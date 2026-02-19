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
    vlm_provider: str = "ollama"
    vlm_model: str = "gemma3:4b"
    vlm_ollama_url: str = "http://127.0.0.1:11434/api/chat"
    vlm_timeout_sec: int = 20
    vlm_keep_alive: str = "10m"
    vlm_use_heuristic_fallback: bool = True
    vlm_raw_log_enabled: bool = True
    vlm_raw_log_path: str = "data/edge/vlm_raw_responses.jsonl"
    request_timeout_sec: int = 5
    request_retries: int = 2
    alert_duration_sec: int = 3
    led_gpio_pin: int = 17
    danger_led_pins: list[int] | None = None
    safe_led_pins: list[int] | None = None
    gpio_pin_mode: str = "BCM"
    buzzer_gpio_pin: int | None = None
    siren_command: str | None = None
    siren_on_sec: float = 0.15
    siren_off_sec: float = 0.08
    simulate_alert_only: bool = True
    tts_enabled: bool = True
    tts_command: str | None = None
    tts_piper_model: str | None = None
    tts_piper_speaker_id: int | None = None
    tts_timeout_sec: int = 8
    tts_use_event_summary_fallback: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "EdgeConfig":
        led_pin_items = [item.strip() for item in os.getenv("EDGE_DANGER_LED_PINS", "").split(",") if item.strip()]
        parsed_led_pins = [int(item) for item in led_pin_items] if led_pin_items else None
        safe_led_pin_items = [item.strip() for item in os.getenv("EDGE_SAFE_LED_PINS", "").split(",") if item.strip()]
        parsed_safe_led_pins = [int(item) for item in safe_led_pin_items] if safe_led_pin_items else None
        buzzer_pin_raw = (os.getenv("EDGE_BUZZER_GPIO_PIN", "") or "").strip()
        parsed_buzzer_pin = int(buzzer_pin_raw) if buzzer_pin_raw else None
        tts_speaker_raw = (os.getenv("EDGE_TTS_PIPER_SPEAKER_ID", "") or "").strip()
        parsed_tts_speaker = int(tts_speaker_raw) if tts_speaker_raw else None

        return cls(
            camera_index=int(os.getenv("EDGE_CAMERA_INDEX", "0")),
            capture_interval_sec=int(os.getenv("EDGE_CAPTURE_INTERVAL_SEC", "10")),
            danger_cooldown_sec=int(os.getenv("EDGE_DANGER_COOLDOWN_SEC", "30")),
            server_base_url=os.getenv("EDGE_SERVER_BASE_URL", "http://127.0.0.1:8000"),
            danger_endpoint=os.getenv("EDGE_DANGER_ENDPOINT", "/events/danger"),
            source_id=os.getenv("EDGE_SOURCE_ID", "jetson-orin-nano-01"),
            vlm_provider=os.getenv("EDGE_VLM_PROVIDER", "ollama").strip().lower(),
            vlm_model=os.getenv("EDGE_VLM_MODEL", "gemma3:4b").strip(),
            vlm_ollama_url=os.getenv("EDGE_VLM_OLLAMA_URL", "http://127.0.0.1:11434/api/chat").strip(),
            vlm_timeout_sec=int(os.getenv("EDGE_VLM_TIMEOUT_SEC", "20")),
            vlm_keep_alive=os.getenv("EDGE_VLM_KEEP_ALIVE", "10m").strip(),
            vlm_use_heuristic_fallback=os.getenv("EDGE_VLM_HEURISTIC_FALLBACK", "true").lower() == "true",
            vlm_raw_log_enabled=os.getenv("EDGE_VLM_RAW_LOG_ENABLED", "true").lower() == "true",
            vlm_raw_log_path=os.getenv("EDGE_VLM_RAW_LOG_PATH", "data/edge/vlm_raw_responses.jsonl").strip(),
            request_timeout_sec=int(os.getenv("EDGE_REQUEST_TIMEOUT_SEC", "5")),
            request_retries=int(os.getenv("EDGE_REQUEST_RETRIES", "2")),
            alert_duration_sec=int(os.getenv("EDGE_ALERT_DURATION_SEC", "3")),
            led_gpio_pin=int(os.getenv("EDGE_LED_GPIO_PIN", "17")),
            danger_led_pins=parsed_led_pins,
            safe_led_pins=parsed_safe_led_pins,
            gpio_pin_mode=(os.getenv("EDGE_GPIO_PIN_MODE", "BCM") or "BCM").strip().upper(),
            buzzer_gpio_pin=parsed_buzzer_pin,
            siren_command=(os.getenv("EDGE_SIREN_COMMAND") or "").strip() or None,
            siren_on_sec=float(os.getenv("EDGE_SIREN_ON_SEC", "0.15")),
            siren_off_sec=float(os.getenv("EDGE_SIREN_OFF_SEC", "0.08")),
            simulate_alert_only=os.getenv("EDGE_SIMULATE_ALERT_ONLY", "true").lower() == "true",
            tts_enabled=os.getenv("EDGE_TTS_ENABLED", "true").lower() == "true",
            tts_command=(os.getenv("EDGE_TTS_COMMAND") or "").strip() or None,
            tts_piper_model=(os.getenv("EDGE_TTS_PIPER_MODEL") or "").strip() or None,
            tts_piper_speaker_id=parsed_tts_speaker,
            tts_timeout_sec=int(os.getenv("EDGE_TTS_TIMEOUT_SEC", "8")),
            tts_use_event_summary_fallback=os.getenv("EDGE_TTS_EVENT_SUMMARY_FALLBACK", "true").lower() == "true",
            log_level=os.getenv("EDGE_LOG_LEVEL", "INFO").upper(),
        )
