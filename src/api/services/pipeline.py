import asyncio

from src.api.models import DangerEvent, DangerResponse
from src.api.services.gemini_tts import GeminiTTSGenerator
from src.api.services.llm_responder import LLMResponder
from src.api.services.local_rag import LocalRAGRetriever
from src.api.services.mcp_rag import MCPRAGRetriever


class DangerProcessingPipeline:
    HAZARD_KEYWORDS: dict[str, tuple[str, ...]] = {
        "fire": ("화재", "연기", "불꽃", "가열", "과열"),
        "fall": ("낙상", "전도", "미끄", "넘어"),
        "intrusion": ("무단", "침입", "위협", "폭력", "이상행동", "비인가"),
        "electrical": ("전기", "누전", "합선", "스파크", "감전"),
    }

    def __init__(
        self,
        mcp_retriever: MCPRAGRetriever,
        local_retriever: LocalRAGRetriever,
        responder: LLMResponder,
        tts_generator: GeminiTTSGenerator,
        mcp_timeout_sec: float = 2.0,
    ) -> None:
        self.mcp_retriever = mcp_retriever
        self.local_retriever = local_retriever
        self.responder = responder
        self.tts_generator = tts_generator
        self.mcp_timeout_sec = mcp_timeout_sec

    def _infer_hazard_hint(self, event: DangerEvent) -> str:
        meta = event.metadata if isinstance(event.metadata, dict) else {}
        scenario = str(meta.get("scenario", "")).strip().lower()
        if scenario in {"fire", "fall", "intrusion", "electrical"}:
            return scenario

        summary = event.summary.lower()
        for hazard, keywords in self.HAZARD_KEYWORDS.items():
            if any(keyword in summary for keyword in keywords):
                return hazard
        return "general"

    def _build_rag_query(self, summary: str, hazard_hint: str) -> str:
        if hazard_hint == "general":
            return summary
        hazard_label = {
            "fire": "화재/연기",
            "fall": "전도/낙상",
            "intrusion": "무단 접근/위험 행동",
            "electrical": "전기 설비 이상",
        }.get(hazard_hint, "일반 위험")
        return f"{hazard_label} 대응 기준으로 검색: {summary}"

    def _score_reference(self, title: str, content: str, tags: list[str], hazard_hint: str) -> int:
        if hazard_hint == "general":
            return 0
        joined = " ".join([title, content, " ".join(tags)]).lower()
        keywords = self.HAZARD_KEYWORDS.get(hazard_hint, ())
        return sum(1 for keyword in keywords if keyword in joined)

    def _rerank_references(self, refs: list, hazard_hint: str) -> list:
        if not refs or hazard_hint == "general":
            return refs

        positives: list[tuple[int, object]] = []
        generals: list[object] = []
        for ref in refs:
            score = self._score_reference(ref.title, ref.content, ref.tags, hazard_hint)
            if score > 0:
                positives.append((score, ref))
            elif ref.id.startswith("general") or "공통" in ref.title:
                generals.append(ref)

        if not positives:
            return refs

        positives.sort(key=lambda item: item[0], reverse=True)
        ranked = [ref for _, ref in positives]
        if generals:
            ranked.append(generals[0])

        top_k = getattr(self.local_retriever, "top_k", 3)
        return ranked[:top_k]

    async def process(self, event: DangerEvent) -> DangerResponse:
        hazard_hint = self._infer_hazard_hint(event)
        rag_query = self._build_rag_query(event.summary, hazard_hint)

        try:
            refs = await asyncio.wait_for(
                self.mcp_retriever.retrieve(rag_query),
                timeout=self.mcp_timeout_sec,
            )
        except Exception:
            refs = []
        refs = self._rerank_references(refs, hazard_hint)
        rag_source = "mcp"
        if not refs:
            refs = self.local_retriever.retrieve(rag_query)
            refs = self._rerank_references(refs, hazard_hint)
            rag_source = "local-fallback"

        operator_response, jetson_summary = await self.responder.build_response(
            situation=event.summary,
            references=refs,
            hazard_hint=hazard_hint,
        )
        jetson_tts_wav_base64 = await self.tts_generator.synthesize_wav_base64(jetson_summary)

        return DangerResponse(
            event_id=event.event_id,
            rag_source=rag_source,
            llm_provider=self.responder.provider_name,
            operator_response=operator_response,
            jetson_tts_summary=jetson_summary,
            jetson_tts_wav_base64=jetson_tts_wav_base64,
            references=refs,
        )
