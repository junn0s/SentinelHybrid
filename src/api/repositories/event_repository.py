import json
from pathlib import Path
from threading import Lock
from typing import Any


class EventRepository:
    def __init__(self, event_log_path: str, response_log_path: str, recents_max: int = 100) -> None:
        self.event_log_path = Path(event_log_path)
        self.response_log_path = Path(response_log_path)
        self.recents_max = recents_max
        self._recent_events: list[dict[str, Any]] = []
        self._recent_responses: list[dict[str, Any]] = []
        self._responses_by_event_id: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _push_recent(self, items: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        items.insert(0, payload)
        if len(items) > self.recents_max:
            items.pop()

    def append_event(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._append_jsonl(self.event_log_path, payload)
            self._push_recent(self._recent_events, payload)

    def append_response(self, event_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._append_jsonl(self.response_log_path, payload)
            self._push_recent(self._recent_responses, payload)
            self._responses_by_event_id[event_id] = payload

    def get_recent_snapshot(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._recent_events)
            responses = list(self._recent_responses)
            return {
                "event_count": len(events),
                "response_count": len(responses),
                "events": events,
                "responses": responses,
            }

    def get_response(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            response = self._responses_by_event_id.get(event_id)
            return dict(response) if response is not None else None
