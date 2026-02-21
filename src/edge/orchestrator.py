import base64
import binascii
import logging
import signal
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import cv2

from src.edge.alerts import AlertController
from src.edge.config import EdgeConfig
from src.edge.server_client import DangerEventClient
from src.edge.vlm_client import VLMClient


def extract_tts_summary(ack: dict[str, Any]) -> str:
    response = ack.get("response")
    if isinstance(response, dict):
        text = response.get("jetson_tts_summary")
        if isinstance(text, str):
            return text.strip()
    return ""


def extract_tts_wav_bytes(ack: dict[str, Any]) -> bytes | None:
    response = ack.get("response")
    if not isinstance(response, dict):
        return None
    encoded = response.get("jetson_tts_wav_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        try:
            return base64.b64decode(encoded)
        except Exception:
            return None


def build_danger_payload(
    cfg: EdgeConfig,
    event_id: str,
    summary: str,
    confidence: float,
    infer_meta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": cfg.source_id,
        "is_danger": True,
        "summary": summary,
        "confidence": confidence,
        "model": cfg.vlm_model,
        "metadata": infer_meta,
    }


class EdgeOrchestrator:
    def __init__(
        self,
        cfg: EdgeConfig,
        alerts: AlertController | None = None,
        client: DangerEventClient | None = None,
        vlm: VLMClient | None = None,
    ) -> None:
        self.cfg = cfg
        self.logger = logging.getLogger(__name__)
        self.alerts = alerts or AlertController(
            led_pin=cfg.led_gpio_pin,
            led_pins=cfg.danger_led_pins,
            safe_led_pins=cfg.safe_led_pins,
            gpio_pin_mode=cfg.gpio_pin_mode,
            buzzer_pin=cfg.buzzer_gpio_pin,
            siren_command=cfg.siren_command,
            siren_on_sec=cfg.siren_on_sec,
            siren_off_sec=cfg.siren_off_sec,
            simulate_only=cfg.simulate_alert_only,
            tts_enabled=cfg.tts_enabled,
            tts_command=cfg.tts_command,
            tts_piper_model=cfg.tts_piper_model,
            tts_piper_speaker_id=cfg.tts_piper_speaker_id,
            tts_timeout_sec=cfg.tts_timeout_sec,
        )
        self.client = client or DangerEventClient(
            base_url=cfg.server_base_url,
            endpoint=cfg.danger_endpoint,
            timeout_sec=cfg.request_timeout_sec,
            retries=cfg.request_retries,
        )
        self.vlm = vlm or VLMClient(
            provider=cfg.vlm_provider,
            model=cfg.vlm_model,
            ollama_url=cfg.vlm_ollama_url,
            timeout_sec=cfg.vlm_timeout_sec,
            keep_alive=cfg.vlm_keep_alive,
            use_heuristic_fallback=cfg.vlm_use_heuristic_fallback,
            raw_log_enabled=cfg.vlm_raw_log_enabled,
            raw_log_path=cfg.vlm_raw_log_path,
        )

        self.logger.info(
            "Alert config: simulate=%s pin_mode=%s danger_led_pins=%s safe_led_pins=%s buzzer_pin=%s siren_cmd=%s",
            cfg.simulate_alert_only,
            cfg.gpio_pin_mode,
            cfg.danger_led_pins if cfg.danger_led_pins else [cfg.led_gpio_pin],
            cfg.safe_led_pins if cfg.safe_led_pins else [],
            cfg.buzzer_gpio_pin,
            bool(cfg.siren_command),
        )

    def run(self) -> None:
        cap = cv2.VideoCapture(self.cfg.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open camera index={self.cfg.camera_index}")

        running = True
        last_capture = 0.0
        last_danger = 0.0

        def _shutdown_handler(signum: int, _frame: object) -> None:
            nonlocal running
            self.logger.info("Signal received (%s). Shutting down...", signum)
            running = False

        signal.signal(signal.SIGINT, _shutdown_handler)
        signal.signal(signal.SIGTERM, _shutdown_handler)

        self.logger.info(
            "Edge loop started: interval=%ss cooldown=%ss",
            self.cfg.capture_interval_sec,
            self.cfg.danger_cooldown_sec,
        )

        try:
            while running:
                ok, frame = cap.read()
                now = time.monotonic()

                if not ok:
                    self.logger.warning("Failed to read frame from camera.")
                    time.sleep(0.2)
                    continue

                if now - last_capture < self.cfg.capture_interval_sec:
                    time.sleep(0.05)
                    continue

                last_capture = now
                is_danger, summary, confidence, infer_meta = self.vlm.analyze_frame(frame)
                self.logger.info(
                    "Frame analyzed: is_danger=%s confidence=%.3f meta=%s",
                    is_danger,
                    confidence,
                    infer_meta,
                )

                if not is_danger:
                    continue

                if now - last_danger < self.cfg.danger_cooldown_sec:
                    self.logger.info("Danger detected but skipped by cooldown.")
                    continue

                last_danger = now
                event_id = f"evt_{uuid.uuid4().hex[:12]}"
                payload = build_danger_payload(
                    cfg=self.cfg,
                    event_id=event_id,
                    summary=summary,
                    confidence=confidence,
                    infer_meta=infer_meta,
                )

                self.alerts.trigger_danger(duration_sec=self.cfg.alert_duration_sec)
                ack = self.client.send(payload)
                if ack is None:
                    self.logger.error("Server send failed. event_id=%s payload=%s", event_id, payload)
                    if self.cfg.server_wav_only:
                        self.logger.warning("EDGE_SERVER_WAV_ONLY=true. Skip text TTS fallback. event_id=%s", event_id)
                        continue
                    if self.cfg.tts_use_event_summary_fallback:
                        self.alerts.speak(summary)
                    continue

                server_wav = extract_tts_wav_bytes(ack)
                if server_wav:
                    if self.alerts.play_wav_bytes(server_wav):
                        continue
                    self.logger.warning("Server WAV playback failed. Falling back to text TTS. event_id=%s", event_id)
                    if self.cfg.server_wav_only:
                        self.logger.warning("EDGE_SERVER_WAV_ONLY=true. Skip text TTS fallback. event_id=%s", event_id)
                        continue
                elif self.cfg.server_wav_only:
                    self.logger.warning(
                        "Server ACK had no WAV. EDGE_SERVER_WAV_ONLY=true so text TTS is skipped. event_id=%s",
                        event_id,
                    )
                    continue

                tts_summary = extract_tts_summary(ack)
                if not tts_summary and self.cfg.tts_use_event_summary_fallback:
                    tts_summary = summary

                if tts_summary:
                    self.alerts.speak(tts_summary)
                else:
                    self.logger.info("No TTS summary returned by server. event_id=%s", event_id)
        finally:
            self.alerts.cleanup()
            cap.release()
            self.logger.info("Edge loop stopped cleanly.")
