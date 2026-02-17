import argparse
import time
import uuid
from datetime import datetime, timezone

import requests


def build_payload(source: str) -> dict:
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "is_danger": True,
        "summary": "작업 구역에서 위험 상황이 감지되었습니다.",
        "confidence": 0.91,
        "model": "gemma3-4b-assumed",
        "metadata": {"mode": "simulation"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Send simulated danger events to SentinelHybrid API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/events/danger")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--source", default="jetson-orin-nano-01")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    for idx in range(args.count):
        payload = build_payload(args.source)
        try:
            resp = requests.post(args.url, json=payload, timeout=args.timeout)
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            jetson_tts = body.get("response", {}).get("jetson_tts_summary", "-")
            rag_source = body.get("response", {}).get("rag_source", "-")
            print(
                f"[{idx+1}/{args.count}] status={resp.status_code} event_id={payload['event_id']} "
                f"rag={rag_source} tts={jetson_tts}"
            )
        except Exception as exc:
            print(f"[{idx+1}/{args.count}] failed: {exc}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
