from src.edge.alerts import AlertController


def test_alert_controller_simulate_smoke() -> None:
    controller = AlertController(
        led_pin=17,
        simulate_only=True,
        tts_enabled=True,
        tts_command=None,
    )
    controller.trigger_danger(duration_sec=0)
    controller.speak("테스트 음성 안내")
    assert controller.play_wav_bytes(b"fake-bytes") is True
    controller.cleanup()
