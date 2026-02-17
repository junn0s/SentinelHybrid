import asyncio
import logging

from src.api.config import ApiConfig
from src.api.models import GeminiSafetyResponse, RAGReference


class LLMResponder:
    HAZARD_KEYWORDS: dict[str, tuple[str, ...]] = {
        "fire": ("화재", "연기", "불꽃", "가열", "과열"),
        "fall": ("낙상", "전도", "미끄", "넘어"),
        "intrusion": ("무단", "침입", "위협", "폭력", "이상행동", "비인가"),
        "electrical": ("전기", "누전", "합선", "스파크", "감전"),
    }

    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._client = None

    @property
    def provider_name(self) -> str:
        if self._client is not None:
            return self.config.llm_provider
        return "fallback-template"

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        if self.config.llm_provider != "gemini":
            return
        if not self.config.google_api_key:
            self.logger.info("GOOGLE_API_KEY not set. Using fallback response template.")
            return

        try:
            from google import genai
        except Exception as exc:  # pragma: no cover
            self.logger.warning("google-genai import failed. Using fallback template: %s", exc)
            return

        self._client = genai.Client(api_key=self.config.google_api_key)

    def _normalize_hazard_hint(self, hazard_hint: str | None) -> str:
        value = (hazard_hint or "").strip().lower()
        if value in {"fire", "fall", "intrusion", "electrical", "general"}:
            return value
        return "general"

    def _contains_cross_hazard_terms(self, text: str, hazard_hint: str) -> bool:
        if hazard_hint == "general":
            return False
        lowered = text.lower()
        for hazard, keywords in self.HAZARD_KEYWORDS.items():
            if hazard == hazard_hint:
                continue
            if any(keyword in lowered for keyword in keywords):
                return True
        return False

    async def build_response(
        self,
        situation: str,
        references: list[RAGReference],
        hazard_hint: str | None = None,
    ) -> tuple[str, str]:
        normalized_hint = self._normalize_hazard_hint(hazard_hint)
        self._ensure_client()
        if self._client is None:
            return self._fallback_response(
                situation=situation,
                references=references,
                hazard_hint=normalized_hint,
            )

        ref_text = "\n".join([f"- {ref.title}: {ref.content}" for ref in references]) or "- 일반 안전 수칙 준수"
        prompt = f"""
너는 산업 안전 관제 AI다.
아래 상황 설명과 참고 매뉴얼을 근거로 대응 지침을 생성하라.
중요: 현장 경보(사이렌/LED)는 이미 발령된 상태다. 따라서 사후 대응 지침을 구체적으로 작성하라.
위험 유형 힌트: {normalized_hint}

[상황 설명]
{situation}

[참고 매뉴얼]
{ref_text}

[출력 규칙]
1) operator_response:
- 3~5문장.
- 첫 문장에서 감지 위험 유형을 명확히 재진술.
- 즉시 통제 조치(작업중지/구역통제/전원차단 중 해당 조치), 인원 보호/대피, 보고(책임자/119/보안), 작업 재개 조건을 포함.
- "주의하세요" 같은 추상 문장만 쓰지 말고 행동을 명령형으로 구체화.
2) jetson_tts_summary:
- 1~2문장.
- 현장 작업자가 즉시 따라야 할 행동을 직접 지시.
- 짧지만 구체적으로 작성.
3) 유형 일관성:
- 위험 유형 힌트가 `general`이 아니면 해당 유형 중심으로만 작성.
- 관련 없는 유형(예: 낙상 상황에서 화재 지침)으로 확장하지 말 것.
"""

        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.config.gemini_model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": GeminiSafetyResponse.model_json_schema(),
                },
            )
            text = getattr(response, "text", None)
            if not text:
                raise RuntimeError("Empty structured response from Gemini")

            parsed = GeminiSafetyResponse.model_validate_json(text)
            operator = parsed.operator_response.strip()
            jetson = parsed.jetson_tts_summary.strip()
            if len(jetson) > 180:
                jetson = jetson[:180].rstrip()
            if not operator or not jetson:
                raise RuntimeError("Structured response missing required fields")

            if self._contains_cross_hazard_terms(f"{operator}\n{jetson}", normalized_hint):
                self.logger.warning(
                    "Gemini response mixed hazard types. Falling back to deterministic template. hint=%s",
                    normalized_hint,
                )
                return self._fallback_response(
                    situation=situation,
                    references=references,
                    hazard_hint=normalized_hint,
                )

            return operator, jetson
        except Exception as exc:
            self.logger.warning("Gemini structured response failed. Fallback template used: %s", exc)
            return self._fallback_response(
                situation=situation,
                references=references,
                hazard_hint=normalized_hint,
            )

    def _infer_hazard_type(
        self,
        situation: str,
        references: list[RAGReference],
        hazard_hint: str | None = None,
    ) -> str:
        normalized_hint = self._normalize_hazard_hint(hazard_hint)
        if normalized_hint != "general":
            return normalized_hint

        joined = " ".join(
            [situation, *[ref.title for ref in references], *[ref.content for ref in references], *[" ".join(ref.tags) for ref in references]]
        ).lower()
        if any(keyword in joined for keyword in ("화재", "연기", "불꽃", "가열", "과열")):
            return "fire"
        if any(keyword in joined for keyword in ("낙상", "전도", "미끄", "넘어")):
            return "fall"
        if any(keyword in joined for keyword in ("무단", "침입", "위협", "폭력", "이상행동", "접근")):
            return "intrusion"
        if any(keyword in joined for keyword in ("전기", "누전", "합선", "스파크", "감전")):
            return "electrical"
        return "general"

    def _fallback_response(
        self,
        situation: str,
        references: list[RAGReference],
        hazard_hint: str | None = None,
    ) -> tuple[str, str]:
        hazard_type = self._infer_hazard_type(
            situation=situation,
            references=references,
            hazard_hint=hazard_hint,
        )
        primary_ref = references[0].content if references else "표준 안전 절차를 적용하십시오."

        operator_templates = {
            "fire": (
                f"감지 상황: {situation} 화재 또는 과열 가능성이 있습니다. 즉시 해당 구역 작업을 중지하고 "
                "전원을 차단한 뒤 인원을 안전 구역으로 대피시키십시오. 초기 진압이 가능한 범위에서 소화기를 사용하고, "
                "확산 징후가 있으면 즉시 119와 현장 책임자에게 보고하십시오. 현장 접근을 통제하고 재점검 완료 전까지 작업 재개를 금지하십시오."
            ),
            "fall": (
                f"감지 상황: {situation} 낙상/전도 위험이 높습니다. 즉시 이동을 중단시키고 미끄럼 위험 구역을 통제하십시오. "
                "부상자 여부를 확인하여 필요 시 응급 처치를 실시하고 관리자에게 즉시 보고하십시오. 위험 원인 제거와 바닥 정리 완료 후에만 작업을 재개하십시오."
            ),
            "intrusion": (
                f"감지 상황: {situation} 무단 접근 또는 위험 행동이 의심됩니다. 즉시 접근 통제 절차를 발동하고 일반 작업자를 "
                "안전 구역으로 이동시키십시오. 보안 담당자에게 즉시 전파하고 상황 악화 시 경찰 신고 절차를 진행하십시오. "
                "CCTV와 이벤트 로그를 보존한 뒤 안전 확인 전까지 작업 재개를 금지하십시오."
            ),
            "electrical": (
                f"감지 상황: {situation} 전기 설비 이상 가능성이 있습니다. 즉시 메인 전원을 차단하고 감전 위험 구역 접근을 금지하십시오. "
                "절연 보호구를 착용한 담당자만 점검하도록 통제하고 임의 복구를 금지하십시오. 설비 담당 승인과 안전 점검 완료 전까지 작업을 재개하지 마십시오."
            ),
            "general": (
                f"감지 상황: {situation} 위험 징후가 확인되었습니다. 즉시 작업을 중단하고 위험 구역을 통제하십시오. "
                "인원을 안전 구역으로 이동시킨 뒤 현장 책임자에게 즉시 보고하고 후속 지시를 받으십시오. "
                "원인 확인 및 재발 방지 조치가 완료되기 전까지 작업을 재개하지 마십시오."
            ),
        }

        tts_templates = {
            "fire": "화재 의심 구역입니다. 즉시 작업을 중단하고 전원을 차단한 뒤 안전 구역으로 대피하세요. 확산 시 즉시 119에 신고하세요.",
            "fall": "낙상 위험 구역입니다. 이동을 즉시 중단하고 미끄럼 구역에서 떨어지세요. 부상자가 있으면 즉시 관리자에게 보고하세요.",
            "intrusion": "무단 접근 의심 상황입니다. 일반 작업자는 안전 구역으로 이동하고 출입을 통제하세요. 보안 담당자 지시에 즉시 따르세요.",
            "electrical": "전기 이상 의심 상황입니다. 전원을 즉시 차단하고 설비 접근을 금지하세요. 절연 보호구 착용 담당자만 점검하세요.",
            "general": "위험 상황입니다. 작업을 즉시 중단하고 안전 구역으로 이동하세요. 현장 책임자 지시에 따라 구역 통제를 유지하세요.",
        }

        operator = operator_templates[hazard_type]
        if references:
            operator = f"{operator} 참고 절차: {primary_ref}"
        jetson = tts_templates[hazard_type]
        return operator, jetson
