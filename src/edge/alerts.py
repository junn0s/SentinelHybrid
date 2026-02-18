import logging
import shlex
import shutil
import subprocess
import time


class AlertController:
    def __init__(
        self,
        led_pin: int,
        simulate_only: bool = True,
        tts_enabled: bool = True,
        tts_command: str | None = None,
        tts_timeout_sec: int = 8,
    ) -> None:
        self.simulate_only = simulate_only
        self.tts_enabled = tts_enabled
        self.tts_timeout_sec = tts_timeout_sec
        self.logger = logging.getLogger(__name__)
        self._led = None
        self._tts_cmd = self._resolve_tts_command(tts_command)

        if self.simulate_only:
            self.logger.info("Alert controller in simulate mode.")
            return

        try:
            from gpiozero import LED  # type: ignore

            self._led = LED(led_pin)
        except Exception as exc:
            self.logger.warning("GPIO LED init failed. Fallback to simulate mode: %s", exc)
            self.simulate_only = True

    def _resolve_tts_command(self, tts_command: str | None) -> list[str] | None:
        if not self.tts_enabled:
            return None

        if tts_command:
            tokens = shlex.split(tts_command)
            if tokens and shutil.which(tokens[0]):
                return tokens
            self.logger.warning("Configured TTS command unavailable: %s", tts_command)
            return None

        for candidate in ("espeak-ng", "espeak", "spd-say", "say"):
            if shutil.which(candidate):
                return [candidate]
        self.logger.warning("No local TTS binary found. Tried espeak-ng/espeak/spd-say/say.")
        return None

    def trigger_danger(self, duration_sec: int = 3) -> None:
        self.logger.warning("Danger alert triggered for %ss", duration_sec)
        if self.simulate_only:
            self.logger.warning("[SIM] RED LED ON, SIREN ON")
            time.sleep(duration_sec)
            self.logger.warning("[SIM] RED LED OFF, SIREN OFF")
            return

        if self._led is not None:
            self._led.on()
        # TODO: Add real buzzer/speaker playback implementation.
        time.sleep(duration_sec)
        if self._led is not None:
            self._led.off()

    def speak(self, text: str) -> None:
        if not self.tts_enabled:
            return

        text = text.strip()
        if not text:
            return

        if self.simulate_only:
            self.logger.warning("[SIM] TTS: %s", text)
            return

        if not self._tts_cmd:
            self.logger.warning("TTS skipped: command not configured or unavailable.")
            return

        try:
            completed = subprocess.run(
                [*self._tts_cmd, text],
                timeout=self.tts_timeout_sec,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if completed.returncode != 0:
                self.logger.warning("TTS command returned non-zero code=%s", completed.returncode)
        except Exception as exc:
            self.logger.warning("TTS playback failed: %s", exc)

    def cleanup(self) -> None:
        if self._led is not None:
            self._led.off()
