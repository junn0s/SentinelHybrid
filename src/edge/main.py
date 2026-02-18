import logging
import signal
import time
import uuid
from datetime import datetime, timezone

import cv2

from src.edge.alerts import AlertController
from src.edge.config import EdgeConfig
from src.edge.server_client import DangerEventClient
from src.edge.vlm_client import VLMClient


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _extract_tts_summary(ack: dict) -> str:
    response = ack.get("response")
    if isinstance(response, dict):
        text = response.get("jetson_tts_summary")
        if isinstance(text, str):
            return text.strip()
    return ""


def run() -> None:
    cfg = EdgeConfig.from_env()
    _setup_logging(cfg.log_level)
    logger = logging.getLogger(__name__)

    alerts = AlertController(
        led_pin=cfg.led_gpio_pin,
        simulate_only=cfg.simulate_alert_only,
        tts_enabled=cfg.tts_enabled,
        tts_command=cfg.tts_command,
        tts_timeout_sec=cfg.tts_timeout_sec,
    )
    client = DangerEventClient(
        base_url=cfg.server_base_url,
        endpoint=cfg.danger_endpoint,
        timeout_sec=cfg.request_timeout_sec,
        retries=cfg.request_retries,
    )
    vlm = VLMClient()

    cap = cv2.VideoCapture(cfg.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open camera index={cfg.camera_index}")

    running = True
    last_capture = 0.0
    last_danger = 0.0

    def _shutdown_handler(signum: int, _frame: object) -> None:
        nonlocal running
        logger.info("Signal received (%s). Shutting down...", signum)
        running = False

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    logger.info("Edge loop started: interval=%ss cooldown=%ss", cfg.capture_interval_sec, cfg.danger_cooldown_sec)

    try:
        while running:
            ok, frame = cap.read()
            now = time.monotonic()

            if not ok:
                logger.warning("Failed to read frame from camera.")
                time.sleep(0.2)
                continue

            if now - last_capture < cfg.capture_interval_sec:
                time.sleep(0.05)
                continue

            last_capture = now
            is_danger, summary, confidence, infer_meta = vlm.analyze_frame(frame)
            logger.info("Frame analyzed: is_danger=%s confidence=%.3f meta=%s", is_danger, confidence, infer_meta)

            if not is_danger:
                continue

            if now - last_danger < cfg.danger_cooldown_sec:
                logger.info("Danger detected but skipped by cooldown.")
                continue

            last_danger = now
            event_id = f"evt_{uuid.uuid4().hex[:12]}"
            payload = {
                "event_id": event_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": cfg.source_id,
                "is_danger": True,
                "summary": summary,
                "confidence": confidence,
                "model": "gemma3-4b-placeholder",
            }

            alerts.trigger_danger(duration_sec=cfg.alert_duration_sec)
            ack = client.send(payload)
            if ack is None:
                logger.error("Server send failed. event_id=%s payload=%s", event_id, payload)
                if cfg.tts_use_event_summary_fallback:
                    alerts.speak(summary)
                continue

            tts_summary = _extract_tts_summary(ack)
            if not tts_summary and cfg.tts_use_event_summary_fallback:
                tts_summary = summary

            if tts_summary:
                alerts.speak(tts_summary)
            else:
                logger.info("No TTS summary returned by server. event_id=%s", event_id)
    finally:
        alerts.cleanup()
        cap.release()
        logger.info("Edge loop stopped cleanly.")


if __name__ == "__main__":
    run()
