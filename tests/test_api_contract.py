import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app_runtime import ApiRuntime
from src.api.config import ApiConfig
from src.api.main import create_app
from src.api.models import DangerResponse
from src.api.repositories.event_repository import EventRepository


class FakePipeline:
    async def process(self, event):  # type: ignore[no-untyped-def]
        return DangerResponse(
            event_id=event.event_id,
            rag_source="mcp",
            llm_provider="gemini",
            operator_response="운영자 대응 문장",
            jetson_tts_summary="현장 TTS 요약",
            jetson_tts_wav_base64="ZmFrZV93YXY=",
            references=[],
        )


class FakeOpsPublisher:
    async def publish(self, event, response):  # type: ignore[no-untyped-def]
        return {"discord": {"status": "ok"}}


def _build_client(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    event_log = tmp_path / "danger_events.jsonl"
    response_log = tmp_path / "danger_responses.jsonl"

    config = ApiConfig(
        event_log_path=str(event_log),
        response_log_path=str(response_log),
        recents_max=100,
    )
    runtime = ApiRuntime(
        config=config,
        pipeline=FakePipeline(),  # type: ignore[arg-type]
        ops_publisher=FakeOpsPublisher(),  # type: ignore[arg-type]
        repository=EventRepository(
            event_log_path=str(event_log),
            response_log_path=str(response_log),
            recents_max=100,
        ),
        admin_dir=Path(__file__).resolve().parents[1] / "src" / "api" / "static" / "admin",
    )
    app = create_app(runtime=runtime)
    return TestClient(app), event_log, response_log


def test_health_contract(tmp_path: Path) -> None:
    client, _, _ = _build_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "rag_mcp_enabled" in body
    assert "llm_provider" in body
    assert "gemini_model" in body


def test_danger_event_contract_and_storage(tmp_path: Path) -> None:
    client, event_log, response_log = _build_client(tmp_path)
    payload = {
        "event_id": "evt_contract_001",
        "timestamp": "2026-02-21T01:02:03+00:00",
        "source": "jetson-orin-nano-01",
        "is_danger": True,
        "summary": "테스트 위험 상황",
        "confidence": 0.93,
        "model": "gemma3:4b",
        "metadata": {"provider": "ollama"},
    }

    post_res = client.post("/events/danger", json=payload)
    assert post_res.status_code == 200
    ack = post_res.json()
    assert ack["status"] == "accepted"
    assert ack["event_id"] == payload["event_id"]
    assert ack["response"]["jetson_tts_wav_base64"] == "ZmFrZV93YXY="

    recent_res = client.get("/events/recent")
    assert recent_res.status_code == 200
    recent = recent_res.json()
    assert recent["event_count"] == 1
    assert recent["response_count"] == 1
    assert "jetson_tts_wav_base64" not in recent["responses"][0]

    detail_res = client.get(f"/events/{payload['event_id']}/response")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["event_id"] == payload["event_id"]
    assert "jetson_tts_wav_base64" not in detail

    event_lines = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
    assert len(event_lines) == 1
    assert event_lines[0]["event_id"] == payload["event_id"]

    response_lines = [json.loads(line) for line in response_log.read_text(encoding="utf-8").splitlines()]
    assert len(response_lines) == 1
    assert response_lines[0]["event_id"] == payload["event_id"]
    assert "jetson_tts_wav_base64" not in response_lines[0]


def test_non_danger_event_is_ignored(tmp_path: Path) -> None:
    client, _, _ = _build_client(tmp_path)
    payload = {
        "event_id": "evt_contract_002",
        "timestamp": "2026-02-21T01:02:03+00:00",
        "source": "jetson-orin-nano-01",
        "is_danger": False,
        "summary": "정상 상황",
        "confidence": 0.12,
        "model": "gemma3:4b",
        "metadata": {"provider": "ollama"},
    }

    post_res = client.post("/events/danger", json=payload)
    assert post_res.status_code == 200
    ack = post_res.json()
    assert ack["status"] == "ignored_non_danger"
    assert ack["event_id"] == payload["event_id"]
    assert ack["response"] is None

    recent_res = client.get("/events/recent")
    assert recent_res.status_code == 200
    recent = recent_res.json()
    assert recent["event_count"] == 1
    assert recent["response_count"] == 0
