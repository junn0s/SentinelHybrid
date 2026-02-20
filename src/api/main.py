import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.config import ApiConfig
from src.api.models import DangerEvent, DangerEventAck, DangerResponse
from src.api.services.llm_responder import LLMResponder
from src.api.services.gemini_tts import GeminiTTSGenerator
from src.api.services.local_rag import LocalRAGRetriever
from src.api.services.mcp_ops import MCPOperationsPublisher
from src.api.services.mcp_rag import MCPRAGRetriever
from src.api.services.pipeline import DangerProcessingPipeline

CONFIG = ApiConfig.from_env()
app = FastAPI(title="SentinelHybrid Danger Event API", version="0.2.0")
LOGGER = logging.getLogger(__name__)

EVENT_LOG_PATH = Path(CONFIG.event_log_path)
RESPONSE_LOG_PATH = Path(CONFIG.response_log_path)
ADMIN_DIR = Path(__file__).resolve().parent / "static" / "admin"

RECENT_EVENTS: list[dict[str, Any]] = []
RECENT_RESPONSES: list[dict[str, Any]] = []
RESPONSES_BY_EVENT_ID: dict[str, dict[str, Any]] = {}

PIPELINE = DangerProcessingPipeline(
    mcp_retriever=MCPRAGRetriever(CONFIG),
    local_retriever=LocalRAGRetriever(top_k=CONFIG.rag_top_k),
    responder=LLMResponder(CONFIG),
    tts_generator=GeminiTTSGenerator(CONFIG),
    mcp_timeout_sec=CONFIG.rag_mcp_timeout_sec,
)
OPS_PUBLISHER = MCPOperationsPublisher(CONFIG)

if ADMIN_DIR.exists():
    app.mount("/admin/static", StaticFiles(directory=str(ADMIN_DIR)), name="admin-static")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _push_recent(items: list[dict[str, Any]], payload: dict[str, Any]) -> None:
    items.insert(0, payload)
    if len(items) > CONFIG.recents_max:
        items.pop()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/admin")


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    page = ADMIN_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Admin UI is not available.")
    return FileResponse(page)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "rag_mcp_enabled": CONFIG.rag_mcp_enabled,
        "llm_provider": CONFIG.llm_provider,
        "gemini_model": CONFIG.gemini_model,
    }


@app.get("/events/recent")
def recent_events() -> dict[str, Any]:
    return {
        "event_count": len(RECENT_EVENTS),
        "response_count": len(RECENT_RESPONSES),
        "events": RECENT_EVENTS,
        "responses": RECENT_RESPONSES,
    }


@app.get("/events/{event_id}/response")
def get_event_response(event_id: str) -> dict[str, Any]:
    response = RESPONSES_BY_EVENT_ID.get(event_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Response not found for event_id")
    return response


@app.post("/events/danger", response_model=DangerEventAck)
async def receive_danger_event(event: DangerEvent) -> DangerEventAck:
    event_payload = event.model_dump(mode="json")
    _append_jsonl(EVENT_LOG_PATH, event_payload)
    _push_recent(RECENT_EVENTS, event_payload)

    if not event.is_danger:
        return DangerEventAck(status="ignored_non_danger", event_id=event.event_id)

    response: DangerResponse = await PIPELINE.process(event)
    ops_result = await OPS_PUBLISHER.publish(event=event, response=response)
    LOGGER.info("MCP ops publish result. event_id=%s result=%s", event.event_id, ops_result)
    # Do not persist large inline WAV payloads in logs or admin polling responses.
    response_payload = response.model_dump(mode="json", exclude={"jetson_tts_wav_base64"})
    _append_jsonl(RESPONSE_LOG_PATH, response_payload)
    _push_recent(RECENT_RESPONSES, response_payload)
    RESPONSES_BY_EVENT_ID[event.event_id] = response_payload

    return DangerEventAck(status="accepted", event_id=event.event_id, response=response)
