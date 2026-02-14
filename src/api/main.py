from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SentinelHybrid Danger Event API", version="0.1.0")


class DangerEvent(BaseModel):
    event_id: str
    timestamp: datetime
    source: str
    is_danger: bool = Field(default=True)
    summary: str
    confidence: float | None = None
    model: str | None = None
    metadata: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events/danger")
def receive_danger_event(event: DangerEvent) -> dict[str, str]:
    # TODO: Connect DB logging, MCP workflow, and Slack notification.
    print(
        f"[DANGER] id={event.event_id} source={event.source} "
        f"summary={event.summary} confidence={event.confidence}"
    )
    return {"status": "accepted", "event_id": event.event_id}

