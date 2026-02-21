import base64

from src.edge.config import EdgeConfig
from src.edge.orchestrator import build_danger_payload, extract_tts_summary, extract_tts_wav_bytes


def test_extract_tts_summary_from_ack() -> None:
    ack = {"response": {"jetson_tts_summary": "  즉시 대피하세요  "}}
    assert extract_tts_summary(ack) == "즉시 대피하세요"


def test_extract_tts_wav_bytes_from_ack() -> None:
    raw = b"wav-bytes"
    ack = {
        "response": {
            "jetson_tts_wav_base64": base64.b64encode(raw).decode("ascii"),
        }
    }
    assert extract_tts_wav_bytes(ack) == raw


def test_build_danger_payload_shape() -> None:
    cfg = EdgeConfig()
    payload = build_danger_payload(
        cfg=cfg,
        event_id="evt_test_001",
        summary="위험 요약",
        confidence=0.91,
        infer_meta={"provider": "ollama", "classification": "DANGER"},
    )
    assert payload["event_id"] == "evt_test_001"
    assert payload["source"] == cfg.source_id
    assert payload["summary"] == "위험 요약"
    assert payload["confidence"] == 0.91
    assert payload["model"] == cfg.vlm_model
    assert payload["metadata"]["classification"] == "DANGER"
    assert payload["is_danger"] is True
    assert isinstance(payload["timestamp"], str)
