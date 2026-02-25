import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

try:
    from ollama import Client
except Exception:  # pragma: no cover - runtime environment dependent
    Client = None  # type: ignore[assignment]


class EdgeVLMResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str
    risk_score: float = Field(ge=0.0, le=1.0)
    hazard_type: str = "unknown"
    summary: str = ""
    evidence: list[str] = Field(default_factory=list)

    @field_validator("label", mode="before")
    @classmethod
    def _normalize_label(cls, value: Any) -> str:
        text = str(value or "").strip().upper()
        if text not in {"DANGER", "SAFE"}:
            raise ValueError("label must be DANGER or SAFE")
        return text

    @field_validator("hazard_type", mode="before")
    @classmethod
    def _normalize_hazard_type(cls, value: Any) -> str:
        text = str(value or "unknown").strip().lower()
        if text in {"fire", "fall", "intrusion", "electrical", "unknown"}:
            return text
        return "unknown"

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: Any) -> str:
        return " ".join(str(value or "").split())

    @field_validator("evidence", mode="before")
    @classmethod
    def _normalize_evidence(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:3]


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
        raw_log_enabled: bool = True,
        raw_log_path: str = "data/edge/vlm_raw_responses.jsonl",
    ) -> None:
        self.provider = provider
        self.model = model
        self.timeout_sec = timeout_sec
        self.keep_alive = keep_alive
        self.use_heuristic_fallback = use_heuristic_fallback
        self.min_danger_score = max(0.0, min(1.0, float(min_danger_score)))
        self.uncertain_as_safe = uncertain_as_safe
        self.raw_log_enabled = raw_log_enabled
        self.raw_log_path = Path(raw_log_path)
        self.logger = logging.getLogger(__name__)

        self.ollama_host = self._derive_ollama_host(ollama_url)

        if self.provider == "ollama" and Client is None:
            raise RuntimeError(
                "ollama Python SDK is not installed. Install with: pip install ollama"
            )

        self.client = Client(host=self.ollama_host, timeout=timeout_sec) if Client else None

    @staticmethod
    def _derive_ollama_host(ollama_url: str) -> str:
        url = (ollama_url or "").strip().rstrip("/")
        if url.endswith("/api/chat"):
            url = url[: -len("/api/chat")]

        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

        if url.startswith("127.0.0.1") or url.startswith("localhost"):
            return f"http://{url}"

        return url

    def analyze_frame(self, frame: np.ndarray) -> tuple[bool, str, float, dict[str, Any]]:
        if self.provider == "ollama":
            try:
                return self._analyze_with_ollama(frame)
            except Exception as exc:
                self.logger.warning(
                    "Ollama VLM call failed. fallback=%s error=%s",
                    self.use_heuristic_fallback,
                    exc,
                )
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
        jpeg_bytes = self._encode_frame_to_jpeg_bytes(frame)

        classify_raw, classify_meta = self._call_ollama(
            prompt=(
                "당신은 산업안전 비전 분석기다.\n"
                "규칙:\n"
                "1) 위험 근거가 불충분하면 label=SAFE, risk_score<=0.49.\n"
                "2) risk_score는 0~1 숫자.\n"
                "3) summary는 상황 설명이다. 보이는 상황을 한국어 1~2문장으로 구체적으로 작성하라.\n"
                "4) 한 번의 판단 결과로 최종 출력한다.\n"
                "5) 반드시 JSON만 출력한다."
            ),
            image=jpeg_bytes,
            response_format_json=True,
        )

        parsed = self._parse_classification(classify_raw)
        parse_status = "pydantic-validated" if parsed is not None else "parse-failed"

        if parsed is None:
            if self.uncertain_as_safe:
                parsed = EdgeVLMResponse(
                    label="SAFE",
                    risk_score=0.0,
                    hazard_type="unknown",
                    evidence=[],
                    summary="",
                )
                parse_status = "parse-failed-safe-default"
            else:
                raise RuntimeError(f"Unexpected classification response: {classify_raw!r}")

        label = parsed.label
        risk_score = parsed.risk_score
        hazard_type = parsed.hazard_type
        evidence = parsed.evidence
        summary_raw = parsed.summary

        decision_notes: list[str] = []
        final_label = label

        if final_label == "DANGER" and risk_score < self.min_danger_score:
            final_label = "SAFE"
            decision_notes.append(
                f"downgraded_by_min_danger_score({risk_score:.2f}<{self.min_danger_score:.2f})"
            )

        is_danger = final_label == "DANGER"
        confidence = self._derive_confidence(final_label=final_label, risk_score=risk_score)

        summary = "특이 위험 상황은 감지되지 않았습니다."
        summary_source = "safe-default"

        if is_danger:
            summary = self._sanitize_summary(summary_raw)
            summary_source = "ollama-summary-json"
            if not summary:
                summary = "위험 징후가 관측되었습니다. 위험 유형 식별을 위해 현장 확인이 필요합니다."
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
                "classification_input": parsed.model_dump(mode="json"),
                "classification_parse_status": parse_status,
                "classification_raw": (classify_raw or "").strip(),
                "classification_response": classify_meta,
                "summary_raw": (summary_raw or "").strip(),
                "summary_used": summary,
                "confidence": confidence,
                "summary_source": summary_source,
                "decision_notes": decision_notes,
            }
        )
        return is_danger, summary, confidence, meta

    def _call_ollama(
        self,
        prompt: str,
        image: bytes,
        response_format_json: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        if self.client is None:
            raise RuntimeError("Ollama client is not initialized.")

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image],
                }
            ],
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.0,
                "top_k": 1,
                "top_p": 0.0,
            },
        }

        if response_format_json:
            kwargs["format"] = EdgeVLMResponse.model_json_schema()

        resp = self.client.chat(**kwargs)

        content: Any = None
        message = getattr(resp, "message", None)
        if message is not None:
            content = getattr(message, "content", None)

        if not isinstance(content, str):
            try:
                content = resp["message"]["content"]
            except Exception as exc:
                raise RuntimeError(
                    f"Invalid Ollama response payload (no message.content): {resp!r}"
                ) from exc

        meta: dict[str, Any] = {}
        metric_keys = (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        )

        for key in metric_keys:
            val = getattr(resp, key, None)
            if val is None and hasattr(resp, "get"):
                try:
                    val = resp.get(key)
                except Exception:
                    val = None
            if val is not None:
                meta[key] = val

        return content, meta

    @staticmethod
    def _encode_frame_to_jpeg_bytes(frame: np.ndarray) -> bytes:
        if frame.dtype != np.uint8:
            frame = np.clip(frame, 0, 255).astype(np.uint8)
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok:
            raise RuntimeError("Failed to encode frame to JPEG.")
        return encoded.tobytes()

    def _parse_classification(self, raw_text: str) -> EdgeVLMResponse | None:
        if not raw_text:
            return None

        text = raw_text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

        try:
            return EdgeVLMResponse.model_validate_json(text)
        except ValidationError as exc:
            self.logger.error("Pydantic validation failed: %s \nRaw text: %s", exc, raw_text)
            return None
        except Exception as exc:
            self.logger.error("Unexpected parsing error: %s", exc)
            return None

    @staticmethod
    def _derive_confidence(final_label: str, risk_score: float) -> float:
        if final_label == "DANGER":
            base = max(0.7, min(0.99, risk_score))
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
