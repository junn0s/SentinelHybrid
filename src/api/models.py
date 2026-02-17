from datetime import datetime

from pydantic import BaseModel, Field


class DangerEvent(BaseModel):
    event_id: str
    timestamp: datetime
    source: str
    is_danger: bool = Field(default=True)
    summary: str
    confidence: float | None = None
    model: str | None = None
    metadata: dict | None = None


class RAGReference(BaseModel):
    id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


class DangerResponse(BaseModel):
    event_id: str
    rag_source: str
    llm_provider: str
    operator_response: str
    jetson_tts_summary: str
    references: list[RAGReference] = Field(default_factory=list)


class DangerEventAck(BaseModel):
    status: str
    event_id: str
    response: DangerResponse | None = None


class GeminiSafetyResponse(BaseModel):
    operator_response: str = Field(
        description=(
            "관리자용 상세 대응 지침. 감지 상황 재진술 + 즉시 통제 + 인원 보호/보고 + 재개 조건을 "
            "포함해 3~5문장으로 작성한다."
        ),
        min_length=80,
        max_length=1000,
    )
    jetson_tts_summary: str = Field(
        description=(
            "Jetson 현장 음성 안내용 1~2문장 지침. 이미 알람이 울린 상태를 전제로 "
            "현장에서 즉시 수행할 행동을 명령형으로 작성한다."
        ),
        min_length=24,
        max_length=180,
    )
