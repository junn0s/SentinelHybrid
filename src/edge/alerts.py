import logging
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time


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
        self.simulate_only = simulate_only
        self.tts_enabled = tts_enabled
        self.tts_piper_model = tts_piper_model
        self.tts_piper_speaker_id = tts_piper_speaker_id
        self.tts_timeout_sec = tts_timeout_sec
        self.siren_on_sec = max(0.01, float(siren_on_sec))
        self.siren_off_sec = max(0.01, float(siren_off_sec))
        self.logger = logging.getLogger(__name__)

        self._danger_leds: list[object] = []
        self._safe_leds: list[object] = []
        self._buzzer = None
        self._jetson_gpio = None
        self._jetson_danger_led_pins: list[int] = []
        self._jetson_safe_led_pins: list[int] = []
        self._jetson_buzzer_pin: int | None = None

        self._siren_cmd = self._resolve_siren_command(siren_command)
        self._tts_cmd = self._resolve_tts_command(tts_command)
        self._gpio_pin_mode = (gpio_pin_mode or "BCM").strip().upper()
        if self._gpio_pin_mode not in {"BCM", "BOARD"}:
            self.logger.warning("Unknown EDGE_GPIO_PIN_MODE=%s. Falling back to BCM.", self._gpio_pin_mode)
            self._gpio_pin_mode = "BCM"

        danger_pins = self._dedupe_pins(led_pins if led_pins else [led_pin])
        safe_pins = self._dedupe_pins(safe_led_pins or [])
        overlap = sorted(set(danger_pins) & set(safe_pins))
        if overlap:
            self.logger.warning(
                "Safe LED pins overlap with danger LED pins: %s. Overlapping pins ignored for safe state.",
                overlap,
            )
            safe_pins = [pin for pin in safe_pins if pin not in overlap]

        if self.simulate_only:
            self.logger.info("Alert controller in simulate mode.")
            return

        using_gpiozero = False
        if self._gpio_pin_mode == "BCM":
            using_gpiozero = self._init_gpiozero(
                danger_pins=danger_pins,
                safe_pins=safe_pins,
                buzzer_pin=buzzer_pin,
            )
        else:
            self.logger.info("Pin mode BOARD selected. Using Jetson.GPIO backend.")

        using_jetson_gpio = False
        if not using_gpiozero:
            using_jetson_gpio = self._init_jetson_gpio(
                danger_pins=danger_pins,
                safe_pins=safe_pins,
                buzzer_pin=buzzer_pin,
            )

        if self._siren_cmd:
            self.logger.info("Siren command enabled: %s", " ".join(self._siren_cmd))

        if not using_gpiozero and not using_jetson_gpio:
            if self._siren_cmd is None:
                self.logger.warning("No hardware alert output initialized. Falling back to simulate mode.")
                self.simulate_only = True
            else:
                self.logger.warning("GPIO backend unavailable. LED/buzzer disabled; siren command-only mode.")
                return

        self._enter_idle_indicator()

    @staticmethod
    def _dedupe_pins(pins: list[int]) -> list[int]:
        unique: list[int] = []
        for pin in pins:
            if pin not in unique:
                unique.append(pin)
        return unique

    def _resolve_tts_command(self, tts_command: str | None) -> list[str] | None:
        if not self.tts_enabled:
            return None

        if tts_command:
            tokens = shlex.split(tts_command)
            if tokens and shutil.which(tokens[0]):
                return tokens
            self.logger.warning("Configured TTS command unavailable: %s", tts_command)
            return None

        # Prefer local neural TTS via Piper when model path + runtime are available.
        if self._can_use_piper():
            return ["piper"]

        for candidate in ("espeak-ng", "espeak", "spd-say", "say"):
            if shutil.which(candidate):
                return [candidate]
        self.logger.warning("No local TTS binary found. Tried piper+ffplay/espeak-ng/espeak/spd-say/say.")
        return None

    def _resolve_siren_command(self, siren_command: str | None) -> list[str] | None:
        if not siren_command:
            return None
        tokens = shlex.split(siren_command)
        if tokens and shutil.which(tokens[0]):
            return tokens
        self.logger.warning("Configured siren command unavailable: %s", siren_command)
        return None

    def _init_gpiozero(self, danger_pins: list[int], safe_pins: list[int], buzzer_pin: int | None) -> bool:
        try:
            from gpiozero import Buzzer, LED  # type: ignore
        except Exception as exc:
            self.logger.warning("gpiozero unavailable or unsupported: %s", exc)
            return False

        for pin in danger_pins:
            try:
                self._danger_leds.append(LED(pin))
            except Exception as exc:
                self.logger.warning("gpiozero danger LED init failed for pin=%s: %s", pin, exc)

        for pin in safe_pins:
            try:
                self._safe_leds.append(LED(pin))
            except Exception as exc:
                self.logger.warning("gpiozero safe LED init failed for pin=%s: %s", pin, exc)

        if buzzer_pin is not None:
            try:
                self._buzzer = Buzzer(buzzer_pin)
            except Exception as exc:
                self.logger.warning("gpiozero buzzer init failed for pin=%s: %s", buzzer_pin, exc)

        if self._danger_leds:
            self.logger.info("gpiozero danger LEDs initialized: pins=%s", danger_pins)
        if self._safe_leds:
            self.logger.info("gpiozero safe LEDs initialized: pins=%s", safe_pins)
        if self._buzzer is not None:
            self.logger.info(
                "gpiozero buzzer initialized: pin=%s on=%.2fs off=%.2fs",
                buzzer_pin,
                self.siren_on_sec,
                self.siren_off_sec,
            )

        return bool(self._danger_leds or self._safe_leds or self._buzzer is not None)

    def _init_jetson_gpio(self, danger_pins: list[int], safe_pins: list[int], buzzer_pin: int | None) -> bool:
        try:
            import Jetson.GPIO as GPIO  # type: ignore
        except Exception as exc:
            self.logger.warning("Jetson.GPIO unavailable: %s", exc)
            return False

        try:
            GPIO.setwarnings(False)
            mode = GPIO.BOARD if self._gpio_pin_mode == "BOARD" else GPIO.BCM
            GPIO.setmode(mode)
            board_ground_pins = {6, 9, 14, 20, 25, 30, 34, 39}

            for pin in danger_pins:
                if self._gpio_pin_mode == "BOARD" and pin in board_ground_pins:
                    self.logger.warning("Pin %s is GND in BOARD mode. Skipping danger LED setup.", pin)
                    continue
                try:
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                    self._jetson_danger_led_pins.append(pin)
                except Exception as exc:
                    self.logger.warning("Jetson GPIO danger LED init failed for pin=%s: %s", pin, exc)

            for pin in safe_pins:
                if self._gpio_pin_mode == "BOARD" and pin in board_ground_pins:
                    self.logger.warning("Pin %s is GND in BOARD mode. Skipping safe LED setup.", pin)
                    continue
                try:
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                    self._jetson_safe_led_pins.append(pin)
                except Exception as exc:
                    self.logger.warning("Jetson GPIO safe LED init failed for pin=%s: %s", pin, exc)

            if buzzer_pin is not None:
                if self._gpio_pin_mode == "BOARD" and buzzer_pin in board_ground_pins:
                    self.logger.warning("Pin %s is GND in BOARD mode. Skipping buzzer setup.", buzzer_pin)
                else:
                    try:
                        GPIO.setup(buzzer_pin, GPIO.OUT, initial=GPIO.LOW)
                        self._jetson_buzzer_pin = buzzer_pin
                    except Exception as exc:
                        self.logger.warning("Jetson GPIO buzzer init failed for pin=%s: %s", buzzer_pin, exc)

            if self._jetson_danger_led_pins:
                self.logger.info(
                    "Jetson GPIO danger LEDs initialized: pins=%s mode=%s",
                    self._jetson_danger_led_pins,
                    self._gpio_pin_mode,
                )
            if self._jetson_safe_led_pins:
                self.logger.info(
                    "Jetson GPIO safe LEDs initialized: pins=%s mode=%s",
                    self._jetson_safe_led_pins,
                    self._gpio_pin_mode,
                )
            if self._jetson_buzzer_pin is not None:
                self.logger.info(
                    "Jetson GPIO buzzer initialized: pin=%s mode=%s on=%.2fs off=%.2fs",
                    self._jetson_buzzer_pin,
                    self._gpio_pin_mode,
                    self.siren_on_sec,
                    self.siren_off_sec,
                )

            if self._jetson_danger_led_pins or self._jetson_safe_led_pins or self._jetson_buzzer_pin is not None:
                self._jetson_gpio = GPIO
                return True

            try:
                GPIO.cleanup()
            except Exception:
                pass
            return False
        except Exception as exc:
            self.logger.warning("Jetson GPIO init failed: %s", exc)
            try:
                GPIO.cleanup()
            except Exception:
                pass
            return False

    def trigger_danger(self, duration_sec: int = 3) -> None:
        self.logger.warning("Danger alert triggered for %ss", duration_sec)
        if self.simulate_only:
            self.logger.warning("[SIM] DANGER LED ON, SAFE LED OFF, SIREN ON")
            time.sleep(duration_sec)
            self.logger.warning("[SIM] DANGER LED OFF, SAFE LED ON, SIREN OFF")
            return

        end_at = time.monotonic() + max(0, duration_sec)
        self._enter_danger_indicator()
        try:
            siren_ok = False
            if self._siren_cmd is not None:
                siren_ok = self._run_siren_command(duration_sec=max(0, duration_sec))

            if not siren_ok:
                if not self._has_buzzer():
                    time.sleep(max(0, duration_sec))
                    return

                while time.monotonic() < end_at:
                    self._buzzer_on()
                    time.sleep(self.siren_on_sec)
                    self._buzzer_off()
                    remaining = end_at - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(self.siren_off_sec, remaining))
        finally:
            self._buzzer_off()
            self._enter_idle_indicator()

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
            if self._tts_cmd[0] == "piper":
                self._speak_with_piper(text)
                return

            if any("{text}" in token for token in self._tts_cmd):
                cmd = [token.replace("{text}", text) for token in self._tts_cmd]
            else:
                cmd = [*self._tts_cmd, text]

            completed = subprocess.run(
                cmd,
                timeout=self.tts_timeout_sec,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if completed.returncode != 0:
                self.logger.warning("TTS command returned non-zero code=%s", completed.returncode)
        except Exception as exc:
            self.logger.warning("TTS playback failed: %s", exc)

    def _can_use_piper(self) -> bool:
        if not shutil.which("piper"):
            return False
        if not shutil.which("ffplay"):
            self.logger.warning("ffplay not installed. Piper output playback unavailable.")
            return False
        if not self.tts_piper_model:
            self.logger.warning("Piper model path not set. Set EDGE_TTS_PIPER_MODEL to use local neural TTS.")
            return False
        model_path = Path(self.tts_piper_model)
        if not model_path.exists():
            self.logger.warning("Piper model not found: %s", model_path)
            return False
        return True

    def _speak_with_piper(self, text: str) -> None:
        if not shutil.which("piper"):
            self.logger.warning("piper not installed. Skipping neural TTS path.")
            return

        if not shutil.which("ffplay"):
            self.logger.warning("ffplay not installed. Cannot play piper audio output.")
            return

        if not self.tts_piper_model:
            self.logger.warning("Piper model path is empty. Set EDGE_TTS_PIPER_MODEL.")
            return

        model_path = Path(self.tts_piper_model)
        if not model_path.exists():
            self.logger.warning("Piper model not found: %s", model_path)
            return

        audio_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="piper_tts_", suffix=".wav", delete=False) as tmp:
                audio_path = tmp.name

            tts_cmd = [
                "piper",
                "--model",
                str(model_path),
                "--output_file",
                audio_path,
            ]
            if self.tts_piper_speaker_id is not None:
                tts_cmd.extend(["--speaker", str(self.tts_piper_speaker_id)])
            tts_run = subprocess.run(
                tts_cmd,
                input=text,
                text=True,
                timeout=self.tts_timeout_sec,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if tts_run.returncode != 0:
                self.logger.warning("piper returned non-zero code=%s", tts_run.returncode)
                return

            play_cmd = ["ffplay", "-nodisp", "-autoexit", audio_path]
            play_run = subprocess.run(
                play_cmd,
                timeout=self.tts_timeout_sec + 5,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if play_run.returncode != 0:
                self.logger.warning("ffplay returned non-zero code=%s while playing piper output", play_run.returncode)
        except Exception as exc:
            self.logger.warning("piper playback failed: %s", exc)
        finally:
            if audio_path:
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def cleanup(self) -> None:
        self._buzzer_off()
        self._danger_led_off()
        self._safe_led_off()
        self._cleanup_jetson_gpio()

    def _enter_idle_indicator(self) -> None:
        self._danger_led_off()
        self._safe_led_on()

    def _enter_danger_indicator(self) -> None:
        self._safe_led_off()
        self._danger_led_on()

    def _danger_led_on(self) -> None:
        self._set_led_group_state(
            gpiozero_leds=self._danger_leds,
            jetson_pins=self._jetson_danger_led_pins,
            on=True,
            label="danger",
        )

    def _danger_led_off(self) -> None:
        self._set_led_group_state(
            gpiozero_leds=self._danger_leds,
            jetson_pins=self._jetson_danger_led_pins,
            on=False,
            label="danger",
        )

    def _safe_led_on(self) -> None:
        self._set_led_group_state(
            gpiozero_leds=self._safe_leds,
            jetson_pins=self._jetson_safe_led_pins,
            on=True,
            label="safe",
        )

    def _safe_led_off(self) -> None:
        self._set_led_group_state(
            gpiozero_leds=self._safe_leds,
            jetson_pins=self._jetson_safe_led_pins,
            on=False,
            label="safe",
        )

    def _set_led_group_state(self, gpiozero_leds: list[object], jetson_pins: list[int], on: bool, label: str) -> None:
        if self._jetson_gpio is not None:
            level = self._jetson_gpio.HIGH if on else self._jetson_gpio.LOW
            for pin in jetson_pins:
                try:
                    self._jetson_gpio.output(pin, level)
                except Exception as exc:
                    self.logger.warning("Jetson GPIO %s LED %s failed for pin=%s: %s", label, "on" if on else "off", pin, exc)

        for led in gpiozero_leds:
            try:
                if on:
                    led.on()
                else:
                    led.off()
            except Exception as exc:
                self.logger.warning("gpiozero %s LED %s failed: %s", label, "on" if on else "off", exc)

    def _has_buzzer(self) -> bool:
        return self._buzzer is not None or (self._jetson_gpio is not None and self._jetson_buzzer_pin is not None)

    def _buzzer_on(self) -> None:
        if self._buzzer is not None:
            try:
                self._buzzer.on()
            except Exception as exc:
                self.logger.warning("Buzzer on failed: %s", exc)
        if self._jetson_gpio is not None and self._jetson_buzzer_pin is not None:
            try:
                self._jetson_gpio.output(self._jetson_buzzer_pin, self._jetson_gpio.HIGH)
            except Exception as exc:
                self.logger.warning("Jetson GPIO buzzer on failed for pin=%s: %s", self._jetson_buzzer_pin, exc)

    def _buzzer_off(self) -> None:
        if self._buzzer is not None:
            try:
                self._buzzer.off()
            except Exception as exc:
                self.logger.warning("Buzzer off failed: %s", exc)
        if self._jetson_gpio is not None and self._jetson_buzzer_pin is not None:
            try:
                self._jetson_gpio.output(self._jetson_buzzer_pin, self._jetson_gpio.LOW)
            except Exception as exc:
                self.logger.warning("Jetson GPIO buzzer off failed for pin=%s: %s", self._jetson_buzzer_pin, exc)

    def _cleanup_jetson_gpio(self) -> None:
        if self._jetson_gpio is None:
            return

        pins: list[int] = []
        pins.extend(self._jetson_danger_led_pins)
        for pin in self._jetson_safe_led_pins:
            if pin not in pins:
                pins.append(pin)
        if self._jetson_buzzer_pin is not None and self._jetson_buzzer_pin not in pins:
            pins.append(self._jetson_buzzer_pin)

        try:
            if pins:
                self._jetson_gpio.cleanup(pins)
            else:
                self._jetson_gpio.cleanup()
        except Exception as exc:
            self.logger.warning("Jetson GPIO cleanup failed: %s", exc)
        finally:
            self._jetson_gpio = None
            self._jetson_danger_led_pins = []
            self._jetson_safe_led_pins = []
            self._jetson_buzzer_pin = None

    def _run_siren_command(self, duration_sec: float) -> bool:
        proc = None
        try:
            proc = subprocess.Popen(
                self._siren_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            probe = min(0.2, max(0, duration_sec))
            if probe > 0:
                time.sleep(probe)
            rc = proc.poll()
            if rc is not None and rc != 0:
                self.logger.warning("Siren command exited early with code=%s", rc)
                return False

            remaining = max(0, duration_sec - probe)
            if remaining > 0:
                time.sleep(remaining)
            return True
        except Exception as exc:
            self.logger.warning("Siren command failed: %s", exc)
            return False
        finally:
            if proc is None:
                return
            try:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=0.8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
