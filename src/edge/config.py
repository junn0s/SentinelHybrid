import os
from dataclasses import dataclass


@dataclass
class EdgeConfig:
    camera_index: int = 0
    capture_interval_sec: int = 10
    danger_cooldown_sec: int = 30
    server_base_url: str = "http://127.0.0.1:8000"
    danger_endpoint: str = "/events/danger"
    source_id: str = "jetson-orin-nano-01"
    request_timeout_sec: int = 5
    request_retries: int = 2
    alert_duration_sec: int = 3
    led_gpio_pin: int = 17
    simulate_alert_only: bool = True
    tts_enabled: bool = True
    tts_command: str | None = None
    tts_timeout_sec: int = 8
    tts_use_event_summary_fallback: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "EdgeConfig":
        return cls(
            camera_index=int(os.getenv("EDGE_CAMERA_INDEX", "0")),
            capture_interval_sec=int(os.getenv("EDGE_CAPTURE_INTERVAL_SEC", "10")),
            danger_cooldown_sec=int(os.getenv("EDGE_DANGER_COOLDOWN_SEC", "30")),
            server_base_url=os.getenv("EDGE_SERVER_BASE_URL", "http://127.0.0.1:8000"),
            danger_endpoint=os.getenv("EDGE_DANGER_ENDPOINT", "/events/danger"),
            source_id=os.getenv("EDGE_SOURCE_ID", "jetson-orin-nano-01"),
            request_timeout_sec=int(os.getenv("EDGE_REQUEST_TIMEOUT_SEC", "5")),
            request_retries=int(os.getenv("EDGE_REQUEST_RETRIES", "2")),
            alert_duration_sec=int(os.getenv("EDGE_ALERT_DURATION_SEC", "3")),
            led_gpio_pin=int(os.getenv("EDGE_LED_GPIO_PIN", "17")),
            simulate_alert_only=os.getenv("EDGE_SIMULATE_ALERT_ONLY", "true").lower() == "true",
            tts_enabled=os.getenv("EDGE_TTS_ENABLED", "true").lower() == "true",
            tts_command=(os.getenv("EDGE_TTS_COMMAND") or "").strip() or None,
            tts_timeout_sec=int(os.getenv("EDGE_TTS_TIMEOUT_SEC", "8")),
            tts_use_event_summary_fallback=os.getenv("EDGE_TTS_EVENT_SUMMARY_FALLBACK", "true").lower() == "true",
            log_level=os.getenv("EDGE_LOG_LEVEL", "INFO").upper(),
        )
