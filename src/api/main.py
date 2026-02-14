import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="SentinelHybrid Danger Event API", version="0.1.0")
EVENT_LOG_PATH = Path("data/events/danger_events.jsonl")
RECENT_EVENTS: list[dict[str, Any]] = []
RECENT_EVENTS_MAX = 50


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


@app.get("/events/recent")
def recent_events() -> dict[str, Any]:
    return {"count": len(RECENT_EVENTS), "events": RECENT_EVENTS}


@app.post("/events/danger")
def receive_danger_event(event: DangerEvent) -> dict[str, str]:
    payload = event.model_dump()
    payload["timestamp"] = event.timestamp.isoformat()

    EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

    RECENT_EVENTS.insert(0, payload)
    if len(RECENT_EVENTS) > RECENT_EVENTS_MAX:
        RECENT_EVENTS.pop()

    print(f"[DANGER] id={event.event_id} source={event.source} summary={event.summary}")
    return {"status": "accepted", "event_id": event.event_id}
