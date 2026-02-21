import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.app_runtime import ApiRuntime
from src.api.models import DangerEvent, DangerEventAck, DangerResponse
from src.api.routes.deps import get_runtime

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/events/recent")
def recent_events(runtime: ApiRuntime = Depends(get_runtime)) -> dict[str, Any]:
    return runtime.repository.get_recent_snapshot()


@router.get("/events/{event_id}/response")
def get_event_response(event_id: str, runtime: ApiRuntime = Depends(get_runtime)) -> dict[str, Any]:
    response = runtime.repository.get_response(event_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Response not found for event_id")
    return response


@router.post("/events/danger", response_model=DangerEventAck)
async def receive_danger_event(event: DangerEvent, runtime: ApiRuntime = Depends(get_runtime)) -> DangerEventAck:
    event_payload = event.model_dump(mode="json")
    runtime.repository.append_event(event_payload)

    if not event.is_danger:
        return DangerEventAck(status="ignored_non_danger", event_id=event.event_id)

    response: DangerResponse = await runtime.pipeline.process(event)
    ops_result = await runtime.ops_publisher.publish(event=event, response=response)
    LOGGER.info("MCP ops publish result. event_id=%s result=%s", event.event_id, ops_result)

    # Do not persist large inline WAV payloads in logs or admin polling responses.
    response_payload = response.model_dump(mode="json", exclude={"jetson_tts_wav_base64"})
    runtime.repository.append_response(event.event_id, response_payload)

    return DangerEventAck(status="accepted", event_id=event.event_id, response=response)
