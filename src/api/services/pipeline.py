import asyncio

from src.api.models import DangerEvent, DangerResponse, RAGReference
from src.api.services.gemini_tts import GeminiTTSGenerator
from src.api.services.hazard_context import HazardContextService, HazardHint
from src.api.services.llm_responder import LLMResponder
from src.api.services.local_rag import LocalRAGRetriever
from src.api.services.mcp_rag import MCPRAGRetriever


class DangerProcessingPipeline:
    def __init__(
        self,
        mcp_retriever: MCPRAGRetriever,
        local_retriever: LocalRAGRetriever,
        responder: LLMResponder,
        tts_generator: GeminiTTSGenerator,
        hazard_context: HazardContextService | None = None,
        mcp_timeout_sec: float = 2.0,
    ) -> None:
        self.mcp_retriever = mcp_retriever
        self.local_retriever = local_retriever
        self.responder = responder
        self.tts_generator = tts_generator
        self.hazard_context = hazard_context or HazardContextService()
        self.mcp_timeout_sec = mcp_timeout_sec

    async def _retrieve_references(
        self,
        rag_query: str,
        hazard_hint: HazardHint,
    ) -> tuple[list[RAGReference], str]:
        try:
            references = await asyncio.wait_for(
                self.mcp_retriever.retrieve(rag_query),
                timeout=self.mcp_timeout_sec,
            )
        except Exception:
            references = []

        top_k = int(getattr(self.local_retriever, "top_k", 3))
        references = self.hazard_context.rerank_references(
            references=references,
            hazard_hint=hazard_hint,
            top_k=top_k,
        )

        rag_source = "mcp"
        if references:
            return references, rag_source

        references = self.local_retriever.retrieve(rag_query)
        references = self.hazard_context.rerank_references(
            references=references,
            hazard_hint=hazard_hint,
            top_k=top_k,
        )
        return references, "local-fallback"

    async def process(self, event: DangerEvent) -> DangerResponse:
        hazard_hint = self.hazard_context.infer_hazard_hint(event)
        rag_query = self.hazard_context.build_rag_query(event.summary, hazard_hint)
        refs, rag_source = await self._retrieve_references(rag_query, hazard_hint)

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
