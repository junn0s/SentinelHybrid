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

        if is_danger:
            summary = "위험 징후가 감지되었습니다. 즉시 주변을 확인하세요."
        else:
            summary = "특이 위험 상황은 감지되지 않았습니다."

        meta = {
            "heuristic": "red_ratio",
            "red_ratio": round(red_ratio, 4),
        }
        return is_danger, summary, confidence, meta

