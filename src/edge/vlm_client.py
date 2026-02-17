import logging
from typing import Any

import numpy as np


class VLMClient:
    """
    MVP placeholder.
    TODO: Replace heuristic with Gemma 3 4B VLM inference call.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    def analyze_frame(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
        # Temporary heuristic: high red channel ratio => potential danger.
        mean_bgr = frame.mean(axis=(0, 1))
        blue, green, red = float(mean_bgr[0]), float(mean_bgr[1]), float(mean_bgr[2])
        red_ratio = red / max(1.0, blue + green)

        is_danger = red_ratio > 0.75
        confidence = min(0.99, max(0.01, red_ratio / 2.0))
        hazard_type = "safe"

        if is_danger:
            if red_ratio > 1.15 and red > 120:
                hazard_type = "fire"
                summary = "작업 구역에서 화재/과열 의심 징후가 감지되었습니다."
            elif red_ratio > 0.95 and red > 95:
                hazard_type = "electrical"
                summary = "전기 설비 주변에서 스파크 의심 징후가 감지되었습니다."
            else:
                hazard_type = "general"
                summary = "작업 구역 경계에서 비정상 위험 행동 징후가 감지되었습니다."
        else:
            summary = "특이 위험 상황은 감지되지 않았습니다."

        meta = {
            "heuristic": "red_ratio",
            "hazard_type": hazard_type,
            "red_ratio": round(red_ratio, 4),
            "mean_blue": round(blue, 2),
            "mean_green": round(green, 2),
            "mean_red": round(red, 2),
        }
        return is_danger, summary, confidence, meta
