import time

import Jetson.GPIO as GPIO

# BOARD pin numbering (physical header pin numbers)
LED_R = 16
LED_G = 18
LED_B = 22


def setup() -> None:
    # Use physical pin numbering mode.
    GPIO.setmode(GPIO.BOARD)

    # Configure output pins and initialize to LOW (off).
    GPIO.setup(LED_R, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LED_G, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(LED_B, GPIO.OUT, initial=GPIO.LOW)


def set_color(r: int, g: int, b: int) -> None:
    # HIGH(1)=on, LOW(0)=off
    GPIO.output(LED_R, r)
    GPIO.output(LED_G, g)
    GPIO.output(LED_B, b)


def main() -> None:
    try:
        setup()
        while True:
            print("위험 감지: 빨간색")
            set_color(1, 0, 0)
            time.sleep(1)

            print("안전 상태: 초록색")
            set_color(0, 1, 0)
            time.sleep(1)

            print("시스템 대기: 파란색")
            set_color(0, 0, 1)
            time.sleep(1)
    except KeyboardInterrupt:
        print("프로그램을 종료합니다.")
    finally:
        # Always release GPIO resources on exit.
        GPIO.cleanup()


if __name__ == "__main__":
    main()
