import argparse
import random
import time
import uuid
from datetime import datetime, timezone

import requests

SCENARIO_SUMMARIES = {
    "fire": [
        "용접 구역 상단에서 연기와 불꽃 흔적이 감지되어 화재 위험이 높습니다.",
        "전기 패널 주변에서 과열 징후와 연기 의심 패턴이 감지되었습니다.",
        "가연성 자재 인근에서 불꽃 반사가 반복되어 초기 화재 가능성이 있습니다.",
    ],
    "fall": [
        "통로 바닥에 액체 누출이 보여 미끄럼 및 낙상 위험이 감지되었습니다.",
        "작업자 이동 구간에서 미끄러운 반사면이 확인되어 전도 위험이 높습니다.",
        "장비 주변 바닥 장애물로 인해 낙상 가능 상황이 감지되었습니다.",
    ],
    "intrusion": [
        "출입 통제 구역 경계에서 비인가 인원 접근 의심 상황이 감지되었습니다.",
        "작업 제한 구역에서 보호장비 미착용 인원의 접근 징후가 포착되었습니다.",
        "야간 통제 구역에서 비정상 동선이 감지되어 보안 확인이 필요합니다.",
    ],
    "electrical": [
        "분전반 인근에서 스파크 의심 광원 변화가 감지되어 감전 위험이 있습니다.",
        "전기 설비 하단 케이블 구간에서 이상 발광 징후가 반복 감지되었습니다.",
        "전원 장치 주변에서 합선 의심 패턴이 감지되어 즉시 점검이 필요합니다.",
    ],
}

SCENARIO_CONFIDENCE_RANGE = {
    "fire": (0.88, 0.97),
    "fall": (0.80, 0.93),
    "intrusion": (0.78, 0.92),
    "electrical": (0.84, 0.96),
}


def _pick_summary(scenario: str) -> tuple[str, str, float]:
    if scenario == "mixed":
        scenario = random.choice(list(SCENARIO_SUMMARIES.keys()))
    summary = random.choice(SCENARIO_SUMMARIES[scenario])
    low, high = SCENARIO_CONFIDENCE_RANGE[scenario]
    confidence = round(random.uniform(low, high), 2)
    return scenario, summary, confidence


def build_payload(source: str, scenario: str) -> dict:
    selected_scenario, summary, confidence = _pick_summary(scenario)
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "is_danger": True,
        "summary": summary,
        "confidence": confidence,
        "model": "gemma3-4b-assumed",
        "metadata": {"mode": "simulation", "scenario": selected_scenario},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Send simulated danger events to SentinelHybrid API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/events/danger")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--source", default="jetson-orin-nano-01")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--scenario",
        default="mixed",
        choices=["mixed", "fire", "fall", "intrusion", "electrical"],
        help="Danger scenario for test payloads.",
    )
    args = parser.parse_args()

    for idx in range(args.count):
        payload = build_payload(args.source, args.scenario)
        try:
            resp = requests.post(args.url, json=payload, timeout=args.timeout)
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            jetson_tts = body.get("response", {}).get("jetson_tts_summary", "-")
            rag_source = body.get("response", {}).get("rag_source", "-")
            scenario = payload.get("metadata", {}).get("scenario", "-")
            summary = payload.get("summary", "-")
            print(
                f"[{idx+1}/{args.count}] status={resp.status_code} event_id={payload['event_id']} "
                f"scenario={scenario} rag={rag_source}\n"
                f"  summary={summary}\n"
                f"  tts={jetson_tts}"
            )
        except Exception as exc:
            print(f"[{idx+1}/{args.count}] failed: {exc}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
