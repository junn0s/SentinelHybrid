import base64
import logging
from typing import Any

import cv2
import numpy as np
import requests


class VLMClient:
    def __init__(
        self,
        provider: str = "ollama",
        model: str = "gemma3:4b",
        ollama_url: str = "http://127.0.0.1:11434/api/chat",
        timeout_sec: int = 20,
        keep_alive: str = "10m",
        use_heuristic_fallback: bool = True,
    ) -> None:
        self.provider = provider
        self.model = model
        self.ollama_url = ollama_url
        self.timeout_sec = timeout_sec
        self.keep_alive = keep_alive
        self.use_heuristic_fallback = use_heuristic_fallback
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

    def analyze_frame(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
        if self.provider == "ollama":
            try:
                return self._analyze_with_ollama(frame)
            except Exception as exc:
                self.logger.warning("Ollama VLM call failed. fallback=%s error=%s", self.use_heuristic_fallback, exc)
        else:
            self.logger.warning("Unsupported EDGE_VLM_PROVIDER=%s", self.provider)

        if self.use_heuristic_fallback:
            is_danger, summary, confidence, meta = self._analyze_with_heuristic(frame)
            meta["fallback_reason"] = "vlm_call_failed_or_unsupported_provider"
            return is_danger, summary, confidence, meta

        raise RuntimeError("VLM analysis failed and heuristic fallback is disabled.")

    def _analyze_with_ollama(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
        encoded_image = self._encode_frame_to_base64(frame)
        classify_raw, classify_meta = self._call_ollama(
            prompt=(
                "당신은 산업안전 감시 분류기다. "
                "출력은 정확히 한 단어만: DANGER 또는 SAFE. "
                "설명, 문장, 구두점, 추가 텍스트 금지."
            ),
            image_base64=encoded_image,
        )
        label = self._normalize_label(classify_raw)
        if label is None:
            raise RuntimeError(f"Unexpected classification response: {classify_raw!r}")

        is_danger = label == "DANGER"
        confidence = 0.93 if is_danger else 0.88
        summary = "특이 위험 상황은 감지되지 않았습니다."
        summary_source = "safe-default"

        if is_danger:
            summary_raw, _summary_meta = self._call_ollama(
                prompt=(
                    "위험 상황이다. "
                    "현장 작업자에게 즉시 필요한 행동만 한국어 한 문장(40자 내외, 명령형)으로 작성하라."
                ),
                image_base64=encoded_image,
            )
            summary = self._sanitize_summary(summary_raw)
            summary_source = "ollama-summary"
            if not summary:
                summary = "즉시 현장을 통제하고 대피 후 관리자에게 보고하세요."
                summary_source = "danger-default"

        meta = {
            "provider": "ollama",
            "model": self.model,
            "classification": label,
            "classification_raw": (classify_raw or "").strip()[:80],
            "summary_source": summary_source,
            "request_prompt_eval_count": classify_meta.get("prompt_eval_count"),
            "request_eval_count": classify_meta.get("eval_count"),
            "request_total_duration_ns": classify_meta.get("total_duration"),
        }
        return is_danger, summary, confidence, meta

    def _call_ollama(self, prompt: str, image_base64: str) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "keep_alive": self.keep_alive,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }
            ],
            "options": {
                "temperature": 0,
            },
        }
        response = self.session.post(self.ollama_url, json=payload, timeout=self.timeout_sec)
        response.raise_for_status()
        body = response.json()
        content = body.get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise RuntimeError(f"Invalid Ollama response payload: {body}")
        return content, body

    @staticmethod
    def _encode_frame_to_base64(frame: np.ndarray) -> str:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise RuntimeError("Failed to encode frame to JPEG.")
        return base64.b64encode(encoded.tobytes()).decode("utf-8")

    @staticmethod
    def _normalize_label(raw_text: str) -> str | None:
        text = (raw_text or "").strip().upper()
        if text.startswith("DANGER"):
            return "DANGER"
        if text.startswith("SAFE"):
            return "SAFE"

        has_danger = "DANGER" in text
        has_safe = "SAFE" in text
        if has_danger and not has_safe:
            return "DANGER"
        if has_safe and not has_danger:
            return "SAFE"
        return None

    @staticmethod
    def _sanitize_summary(raw_text: str) -> str:
        text = " ".join((raw_text or "").split())
        if len(text) > 120:
            text = text[:120].rstrip()
        return text

    def _analyze_with_heuristic(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
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
            "provider": "heuristic",
            "heuristic": "red_ratio",
            "hazard_type": hazard_type,
            "red_ratio": round(red_ratio, 4),
            "mean_blue": round(blue, 2),
            "mean_green": round(green, 2),
            "mean_red": round(red, 2),
        }
        return is_danger, summary, confidence, meta
