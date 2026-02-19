import logging
import shlex
import shutil
import subprocess
import time


class AlertController:
    def __init__(
        self,
        led_pin: int,
        led_pins: list[int] | None = None,
        buzzer_pin: int | None = None,
        siren_command: str | None = None,
        siren_on_sec: float = 0.15,
        siren_off_sec: float = 0.08,
        simulate_only: bool = True,
        tts_enabled: bool = True,
        tts_command: str | None = None,
        tts_timeout_sec: int = 8,
    ) -> None:
        self.simulate_only = simulate_only
        self.tts_enabled = tts_enabled
        self.tts_timeout_sec = tts_timeout_sec
        self.siren_on_sec = max(0.01, float(siren_on_sec))
        self.siren_off_sec = max(0.01, float(siren_off_sec))
        self.logger = logging.getLogger(__name__)
        self._leds: list[object] = []
        self._buzzer = None
        self._siren_cmd = self._resolve_siren_command(siren_command)
        self._tts_cmd = self._resolve_tts_command(tts_command)

        if self.simulate_only:
            self.logger.info("Alert controller in simulate mode.")
            return

        try:
            from gpiozero import Buzzer, LED  # type: ignore

            pin_candidates = led_pins if led_pins else [led_pin]
            unique_pins: list[int] = []
            for pin in pin_candidates:
                if pin not in unique_pins:
                    unique_pins.append(pin)

            for pin in unique_pins:
                self._leds.append(LED(pin))

            if buzzer_pin is not None:
                self._buzzer = Buzzer(buzzer_pin)

            if self._leds:
                self.logger.info("GPIO LEDs initialized: pins=%s", unique_pins)
            if self._buzzer is not None:
                self.logger.info(
                    "GPIO buzzer initialized: pin=%s on=%.2fs off=%.2fs",
                    buzzer_pin,
                    self.siren_on_sec,
                    self.siren_off_sec,
                )
            if self._siren_cmd:
                self.logger.info("Siren command enabled: %s", " ".join(self._siren_cmd))
        except Exception as exc:
            self.logger.warning("GPIO alert init failed. Fallback to simulate mode: %s", exc)
            self.simulate_only = True
            self._leds = []
            self._buzzer = None

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

    def _resolve_siren_command(self, siren_command: str | None) -> list[str] | None:
        if not siren_command:
            return None
        tokens = shlex.split(siren_command)
        if tokens and shutil.which(tokens[0]):
            return tokens
        self.logger.warning("Configured siren command unavailable: %s", siren_command)
        return None

    def trigger_danger(self, duration_sec: int = 3) -> None:
        self.logger.warning("Danger alert triggered for %ss", duration_sec)
        if self.simulate_only:
            self.logger.warning("[SIM] RED LED ON, SIREN ON")
            time.sleep(duration_sec)
            self.logger.warning("[SIM] RED LED OFF, SIREN OFF")
            return

        end_at = time.monotonic() + max(0, duration_sec)
        self._led_on()
        try:
            if self._siren_cmd is not None:
                self._run_siren_command(duration_sec=max(0, duration_sec))
                return

            if self._buzzer is None:
                time.sleep(max(0, duration_sec))
                return

            while time.monotonic() < end_at:
                self._buzzer.on()
                time.sleep(self.siren_on_sec)
                self._buzzer.off()
                remaining = end_at - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(self.siren_off_sec, remaining))
        finally:
            if self._buzzer is not None:
                self._buzzer.off()
            self._led_off()

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
        if self._buzzer is not None:
            self._buzzer.off()
        self._led_off()

    def _led_on(self) -> None:
        for led in self._leds:
            try:
                led.on()
            except Exception as exc:
                self.logger.warning("LED on failed: %s", exc)

    def _led_off(self) -> None:
        for led in self._leds:
            try:
                led.off()
            except Exception as exc:
                self.logger.warning("LED off failed: %s", exc)

    def _run_siren_command(self, duration_sec: float) -> None:
        proc = None
        try:
            proc = subprocess.Popen(
                self._siren_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(duration_sec)
        except Exception as exc:
            self.logger.warning("Siren command failed: %s", exc)
        finally:
            if proc is None:
                return
            try:
                proc.terminate()
                proc.wait(timeout=0.8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
