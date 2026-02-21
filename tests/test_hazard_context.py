from datetime import datetime, timezone

from src.api.models import DangerEvent, RAGReference
from src.api.services.hazard_context import HazardContextService


def _event(summary: str, metadata: dict | None = None) -> DangerEvent:
    return DangerEvent(
        event_id="evt_test",
        timestamp=datetime.now(timezone.utc),
        source="test",
        summary=summary,
        metadata=metadata,
    )


def test_infer_hazard_hint_from_metadata_scenario() -> None:
    service = HazardContextService()
    event = _event("일반 상황", metadata={"scenario": "fire"})
    assert service.infer_hazard_hint(event) == "fire"


def test_infer_hazard_hint_from_summary_keyword() -> None:
    service = HazardContextService()
    event = _event("바닥이 젖어 있어 넘어질 위험이 높습니다")
    assert service.infer_hazard_hint(event) == "fall"


def test_build_rag_query_includes_hazard_label() -> None:
    service = HazardContextService()
    assert (
        service.build_rag_query("연기가 발생했습니다", "fire")
        == "화재/연기 대응 기준으로 검색: 연기가 발생했습니다"
    )
    assert service.build_rag_query("원인 불명 위험", "general") == "원인 불명 위험"


def test_rerank_references_prioritizes_hazard_and_common() -> None:
    service = HazardContextService()
    refs = [
        RAGReference(id="fire-1", title="화재 대응", content="화재 시 대피", tags=["화재"]),
        RAGReference(id="fall-1", title="전도 위험 대응", content="미끄럼과 낙상 예방", tags=["낙상"]),
        RAGReference(
            id="general-1",
            title="일반 위험 대응 공통 절차",
            content="공통 절차",
            tags=[],
        ),
    ]
    ranked = service.rerank_references(refs, "fall", top_k=2)
    assert [ref.id for ref in ranked] == ["fall-1", "general-1"]


def test_rerank_references_keeps_order_when_no_positive_match() -> None:
    service = HazardContextService()
    refs = [
        RAGReference(id="intrusion-1", title="출입 통제", content="무단 접근 대응", tags=["보안"]),
        RAGReference(id="general-1", title="일반 위험 대응 공통 절차", content="공통 절차", tags=[]),
    ]
    ranked = service.rerank_references(refs, "electrical", top_k=3)
    assert [ref.id for ref in ranked] == ["intrusion-1", "general-1"]
