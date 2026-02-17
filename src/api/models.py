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
        description="관리자용 상세 대응 지침. 2~4문장으로 작성한다."
    )
    jetson_tts_summary: str = Field(
        description="Jetson 현장 음성 안내용 한 문장. 최대 40자 권장."
    )
