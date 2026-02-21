from typing import Literal, cast

from src.api.models import DangerEvent, RAGReference

HazardHint = Literal["fire", "fall", "intrusion", "electrical", "general"]


class HazardContextService:
    HAZARD_KEYWORDS: dict[str, tuple[str, ...]] = {
        "fire": ("화재", "연기", "불꽃", "가열", "과열"),
        "fall": ("낙상", "전도", "미끄", "넘어"),
        "intrusion": ("무단", "침입", "위협", "폭력", "이상행동", "비인가"),
        "electrical": ("전기", "누전", "합선", "스파크", "감전"),
    }

    HAZARD_LABELS: dict[str, str] = {
        "fire": "화재/연기",
        "fall": "전도/낙상",
        "intrusion": "무단 접근/위험 행동",
        "electrical": "전기 설비 이상",
        "general": "일반 위험",
    }

    def infer_hazard_hint(self, event: DangerEvent) -> HazardHint:
        meta = event.metadata if isinstance(event.metadata, dict) else {}
        scenario = str(meta.get("scenario", "")).strip().lower()
        if scenario in {"fire", "fall", "intrusion", "electrical"}:
            return cast(HazardHint, scenario)

        summary = event.summary.lower()
        for hazard, keywords in self.HAZARD_KEYWORDS.items():
            if any(keyword in summary for keyword in keywords):
                return cast(HazardHint, hazard)
        return "general"

    def build_rag_query(self, summary: str, hazard_hint: HazardHint) -> str:
        if hazard_hint == "general":
            return summary
        hazard_label = self.HAZARD_LABELS.get(hazard_hint, "일반 위험")
        return f"{hazard_label} 대응 기준으로 검색: {summary}"

    def _score_reference(self, reference: RAGReference, hazard_hint: HazardHint) -> int:
        if hazard_hint == "general":
            return 0
        joined = " ".join(
            [reference.title, reference.content, " ".join(reference.tags)]
        ).lower()
        keywords = self.HAZARD_KEYWORDS.get(hazard_hint, ())
        return sum(1 for keyword in keywords if keyword in joined)

    def rerank_references(
        self,
        references: list[RAGReference],
        hazard_hint: HazardHint,
        top_k: int,
    ) -> list[RAGReference]:
        if not references or hazard_hint == "general":
            return references

        positives: list[tuple[int, RAGReference]] = []
        generals: list[RAGReference] = []
        for ref in references:
            score = self._score_reference(ref, hazard_hint)
            if score > 0:
                positives.append((score, ref))
            elif ref.id.startswith("general") or "공통" in ref.title:
                generals.append(ref)

        if not positives:
            return references

        positives.sort(key=lambda item: item[0], reverse=True)
        ranked = [ref for _, ref in positives]
        if generals:
            ranked.append(generals[0])

        return ranked[:top_k] if top_k > 0 else ranked
