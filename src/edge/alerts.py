import logging

from src.edge.alerts_indicator import IndicatorOutput
from src.edge.alerts_speech import SpeechOutput


class AlertController:
    def __init__(
        self,
        led_pin: int,
        led_pins: list[int] | None = None,
        safe_led_pins: list[int] | None = None,
        gpio_pin_mode: str = "BCM",
        buzzer_pin: int | None = None,
        siren_command: str | None = None,
        siren_on_sec: float = 0.15,
        siren_off_sec: float = 0.08,
        simulate_only: bool = True,
        tts_enabled: bool = True,
        tts_command: str | None = None,
        tts_piper_model: str | None = None,
        tts_piper_speaker_id: int | None = None,
        tts_timeout_sec: int = 8,
    ) -> None:
        self.logger = logging.getLogger(__name__)

        self.indicator = IndicatorOutput(
            led_pin=led_pin,
            led_pins=led_pins,
            safe_led_pins=safe_led_pins,
            gpio_pin_mode=gpio_pin_mode,
            buzzer_pin=buzzer_pin,
            siren_command=siren_command,
            siren_on_sec=siren_on_sec,
            siren_off_sec=siren_off_sec,
            simulate_only=simulate_only,
            logger=self.logger,
        )
        self.simulate_only = self.indicator.simulate_only

        if simulate_only:
            self.logger.info("Alert controller in simulate mode.")

        self.speech = SpeechOutput(
            simulate_only=self.simulate_only,
            tts_enabled=tts_enabled,
            tts_command=tts_command,
            tts_piper_model=tts_piper_model,
            tts_piper_speaker_id=tts_piper_speaker_id,
            tts_timeout_sec=tts_timeout_sec,
            logger=self.logger,
        )

    def trigger_danger(self, duration_sec: int = 3) -> None:
        self.indicator.trigger_danger(duration_sec=duration_sec)

    def speak(self, text: str) -> None:
        self.speech.speak(text)

    def play_wav_bytes(self, wav_bytes: bytes) -> bool:
        return self.speech.play_wav_bytes(wav_bytes)

    def cleanup(self) -> None:
        self.indicator.cleanup()
