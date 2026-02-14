import logging
import time
from typing import Any

import requests


class DangerEventClient:
    def __init__(self, base_url: str, endpoint: str, timeout_sec: int = 5, retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint
        self.timeout_sec = timeout_sec
        self.retries = retries
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

    def send(self, payload: dict[str, Any]) -> bool:
        url = f"{self.base_url}{self.endpoint}"
        last_error = None

        for attempt in range(1, self.retries + 2):
            try:
                response = self.session.post(url, json=payload, timeout=self.timeout_sec)
                if response.ok:
                    self.logger.info("Danger event sent: status=%s event_id=%s", response.status_code, payload["event_id"])
                    return True
                last_error = RuntimeError(f"status={response.status_code} body={response.text[:200]}")
            except Exception as exc:
                last_error = exc

            self.logger.warning("Send failed (attempt %s): %s", attempt, last_error)
            time.sleep(0.4)

        self.logger.error("Danger event send failed after retries: %s", last_error)
        return False

