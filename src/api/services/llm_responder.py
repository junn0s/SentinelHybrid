import asyncio
import logging

from src.api.config import ApiConfig
from src.api.models import GeminiSafetyResponse, RAGReference


class LLMResponder:
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

    async def build_response(self, situation: str, references: list[RAGReference]) -> tuple[str, str]:
        self._ensure_client()
        if self._client is None:
            return self._fallback_response(situation=situation, references=references)

        ref_text = "\n".join([f"- {ref.title}: {ref.content}" for ref in references]) or "- 일반 안전 수칙 준수"
        prompt = f"""
너는 산업 안전 관제 AI다.
아래 상황 설명과 참고 매뉴얼을 근거로 대응 지침을 생성하라.

[상황 설명]
{situation}

[참고 매뉴얼]
{ref_text}
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
            jetson = parsed.jetson_tts_summary.strip()[:40]
            if not operator or not jetson:
                raise RuntimeError("Structured response missing required fields")
            return operator, jetson
        except Exception as exc:
            self.logger.warning("Gemini structured response failed. Fallback template used: %s", exc)
            return self._fallback_response(situation=situation, references=references)

    def _fallback_response(self, situation: str, references: list[RAGReference]) -> tuple[str, str]:
        if references:
            ref = references[0]
            operator = (
                f"감지 상황: {situation}\n"
                f"권장 대응: {ref.content}\n"
                "현장 인원 안전 확보 후 관리자 보고 및 로그를 유지하세요."
            )
            jetson = f"주의: {ref.title} 절차를 즉시 수행하세요."
            return operator, jetson[:40]

        operator = (
            f"감지 상황: {situation}\n"
            "현장 경고를 유지하고 인원 안전을 우선 확보한 뒤 관리자에게 보고하세요."
        )
        jetson = "주의: 위험 상황입니다. 안전 절차를 수행하세요."
        return operator, jetson[:40]

