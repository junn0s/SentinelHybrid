import logging
import time


class AlertController:
    def __init__(self, led_pin: int, simulate_only: bool = True) -> None:
        self.simulate_only = simulate_only
        self.logger = logging.getLogger(__name__)
        self._led = None

        if self.simulate_only:
            self.logger.info("Alert controller in simulate mode.")
            return

        try:
            from gpiozero import LED  # type: ignore

            self._led = LED(led_pin)
        except Exception as exc:
            self.logger.warning("GPIO LED init failed. Fallback to simulate mode: %s", exc)
            self.simulate_only = True

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

    def cleanup(self) -> None:
        if self._led is not None:
            self._led.off()

