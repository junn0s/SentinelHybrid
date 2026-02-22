import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
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
        min_danger_score: float = 0.7,
        uncertain_as_safe: bool = True,
        danger_double_check: bool = True,
        raw_log_enabled: bool = True,
        raw_log_path: str = "data/edge/vlm_raw_responses.jsonl",
    ) -> None:
        self.provider = provider
        self.model = model
        self.ollama_url = ollama_url
        self.timeout_sec = timeout_sec
        self.keep_alive = keep_alive
        self.use_heuristic_fallback = use_heuristic_fallback
        self.min_danger_score = max(0.0, min(1.0, float(min_danger_score)))
        self.uncertain_as_safe = uncertain_as_safe
        self.danger_double_check = danger_double_check
        self.raw_log_enabled = raw_log_enabled
        self.raw_log_path = Path(raw_log_path)
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

    def analyze_frame(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
        if self.provider == "ollama":
            try:
                return self._analyze_with_ollama(frame)
            except Exception as exc:
                self.logger.warning("Ollama VLM call failed. fallback=%s error=%s", self.use_heuristic_fallback, exc)
                self._write_raw_log(
                    {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "status": "ollama-error",
                        "provider": self.provider,
                        "model": self.model,
                        "error": str(exc),
                    }
                )
        else:
            self.logger.warning("Unsupported EDGE_VLM_PROVIDER=%s", self.provider)

        if self.use_heuristic_fallback:
            is_danger, summary, confidence, meta = self._analyze_with_heuristic(frame)
            meta["fallback_reason"] = "vlm_call_failed_or_unsupported_provider"
            self._write_raw_log(
                {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "heuristic-fallback",
                    "provider": self.provider,
                    "model": self.model,
                    "is_danger": is_danger,
                    "summary": summary,
                    "confidence": confidence,
                    "meta": meta,
                }
            )
            return is_danger, summary, confidence, meta

        raise RuntimeError("VLM analysis failed and heuristic fallback is disabled.")

    def _analyze_with_ollama(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
        encoded_image = self._encode_frame_to_base64(frame)

        classify_raw, classify_meta = self._call_ollama(
            prompt=(
                "당신은 산업안전 이진 분류기다.\n"
                "아래 JSON 객체 하나만 출력하라. 다른 문장/설명/코드블록 금지.\n"
                "{\"label\":\"DANGER|SAFE\",\"risk_score\":0.0,\"hazard_type\":\"fire|fall|intrusion|electrical|unknown\",\"evidence\":[\"근거1\",\"근거2\"]}\n"
                "규칙: 위험 근거가 불충분하거나 애매하면 label=SAFE, risk_score<=0.49.\n"
                "risk_score는 0~1 사이 숫자."
            ),
            image_base64=encoded_image,
        )

        parsed = self._parse_classification(classify_raw)
        parse_status = "json-parsed" if parsed is not None else "parse-failed"
        if parsed is None:
            if self.uncertain_as_safe:
                parsed = {
                    "label": "SAFE",
                    "risk_score": 0.0,
                    "hazard_type": "unknown",
                    "evidence": [],
                }
                parse_status = "parse-failed-safe-default"
            else:
                raise RuntimeError(f"Unexpected classification response: {classify_raw!r}")

        label = parsed["label"]
        risk_score = parsed["risk_score"]
        hazard_type = parsed["hazard_type"]
        evidence = parsed["evidence"]

        decision_notes: list[str] = []
        final_label = label

        if final_label == "DANGER" and risk_score < self.min_danger_score:
            final_label = "SAFE"
            decision_notes.append(
                f"downgraded_by_min_danger_score({risk_score:.2f}<{self.min_danger_score:.2f})"
            )

        verify_raw = ""
        verify_meta: dict[str, Any] = {}
        verify_label: str | None = None
        if final_label == "DANGER" and self.danger_double_check:
            verify_raw, verify_meta = self._call_ollama(
                prompt=(
                    "재검증 단계다. 즉시 대피/통제가 필요한 명백한 위험이면 DANGER, 아니면 SAFE. "
                    "애매하면 SAFE. 출력은 한 단어만: DANGER 또는 SAFE."
                ),
                image_base64=encoded_image,
            )
            verify_label = self._normalize_label(verify_raw)
            if verify_label != "DANGER":
                final_label = "SAFE"
                decision_notes.append("downgraded_by_double_check")

        is_danger = final_label == "DANGER"
        confidence = self._derive_confidence(
            final_label=final_label,
            risk_score=risk_score,
            verify_label=verify_label,
        )

        summary = "특이 위험 상황은 감지되지 않았습니다."
        summary_source = "safe-default"
        summary_raw = ""
        summary_meta: dict[str, Any] = {}

        if is_danger:
            summary_raw, summary_meta = self._call_ollama(
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
            "classification": final_label,
            "classification_raw": (classify_raw or "").strip()[:200],
            "classification_parse_status": parse_status,
            "label_before_guardrail": label,
            "risk_score": risk_score,
            "min_danger_score": self.min_danger_score,
            "hazard_type": hazard_type,
            "evidence": evidence,
            "danger_double_check": self.danger_double_check,
            "double_check_raw": (verify_raw or "").strip()[:80],
            "double_check_label": verify_label,
            "decision_notes": decision_notes,
            "summary_source": summary_source,
            "request_prompt_eval_count": classify_meta.get("prompt_eval_count"),
            "request_eval_count": classify_meta.get("eval_count"),
            "request_total_duration_ns": classify_meta.get("total_duration"),
        }
        self._write_raw_log(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "status": "ok",
                "provider": "ollama",
                "model": self.model,
                "classification_final": final_label,
                "classification_input": parsed,
                "classification_parse_status": parse_status,
                "classification_raw": (classify_raw or "").strip(),
                "classification_response": classify_meta,
                "double_check_raw": (verify_raw or "").strip(),
                "double_check_response": verify_meta,
                "summary_raw": (summary_raw or "").strip(),
                "summary_response": summary_meta,
                "summary_used": summary,
                "confidence": confidence,
                "summary_source": summary_source,
                "decision_notes": decision_notes,
            }
        )
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

    def _parse_classification(self, raw_text: str) -> dict[str, Any] | None:
        if not raw_text:
            return None

        text = raw_text.strip()
        parsed_obj: dict[str, Any] | None = None

        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                parsed_obj = loaded
        except Exception:
            parsed_obj = None

        if parsed_obj is None:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    loaded = json.loads(text[start : end + 1])
                    if isinstance(loaded, dict):
                        parsed_obj = loaded
                except Exception:
                    parsed_obj = None

        if parsed_obj is None:
            label = self._normalize_label(text)
            if label is None:
                return None
            return {
                "label": label,
                "risk_score": 0.55 if label == "DANGER" else 0.45,
                "hazard_type": "unknown",
                "evidence": [],
            }

        label = self._normalize_label(str(parsed_obj.get("label", "")))
        if label is None:
            return None

        risk_score = self._coerce_score(parsed_obj.get("risk_score"))
        if risk_score is None:
            risk_score = 0.5 if label == "DANGER" else 0.2

        hazard_type = str(parsed_obj.get("hazard_type", "unknown") or "unknown").strip().lower()
        if not hazard_type:
            hazard_type = "unknown"

        evidence_raw = parsed_obj.get("evidence", [])
        evidence: list[str] = []
        if isinstance(evidence_raw, list):
            evidence = [str(item).strip() for item in evidence_raw if str(item).strip()]

        return {
            "label": label,
            "risk_score": risk_score,
            "hazard_type": hazard_type,
            "evidence": evidence[:3],
        }

    @staticmethod
    def _coerce_score(value: Any) -> float | None:
        try:
            score = float(value)
        except Exception:
            return None
        if score < 0:
            score = 0.0
        if score > 1:
            score = 1.0
        return score

    @staticmethod
    def _derive_confidence(final_label: str, risk_score: float, verify_label: str | None) -> float:
        if final_label == "DANGER":
            base = max(0.7, min(0.99, risk_score))
            if verify_label == "DANGER":
                base = min(0.99, base + 0.04)
            return round(base, 3)

        safe_conf = max(0.51, 1.0 - risk_score)
        return round(min(0.95, safe_conf), 3)

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

    def _write_raw_log(self, payload: dict[str, Any]) -> None:
        if not self.raw_log_enabled:
            return

        try:
            self.raw_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.raw_log_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            self.logger.warning("Failed to write VLM raw log: %s", exc)
