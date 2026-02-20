import asyncio
import base64
import io
import logging
import wave
from typing import Any

from src.api.config import ApiConfig


class GeminiTTSGenerator:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        if not self.config.gemini_tts_enabled:
            return
        if not self.config.google_api_key:
            self.logger.info("GOOGLE_API_KEY not set. Server-side Gemini TTS disabled.")
            return

        try:
            from google import genai
        except Exception as exc:  # pragma: no cover
            self.logger.warning("google-genai import failed. Server-side Gemini TTS disabled: %s", exc)
            return

        self._client = genai.Client(api_key=self.config.google_api_key)

    def _build_prompt(self, text: str) -> str:
        style = (self.config.gemini_tts_style_prompt or "").strip()
        if not style:
            return text
        return f"{style}\n\n{text}"

    @staticmethod
    def _extract_inline_audio_bytes(response: Any) -> bytes:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            parts = getattr(content, "parts", None) or []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is None:
                    continue
                data = getattr(inline_data, "data", None)
                if not data:
                    continue
                if isinstance(data, bytes):
                    return data
                if isinstance(data, str):
                    return base64.b64decode(data)
        raise RuntimeError("Gemini TTS response did not include audio data")

    def _pcm_to_wav_bytes(self, pcm_bytes: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(max(1, int(self.config.gemini_tts_channels)))
            wf.setsampwidth(max(1, int(self.config.gemini_tts_sample_width)))
            wf.setframerate(max(8000, int(self.config.gemini_tts_rate_hz)))
            wf.writeframes(pcm_bytes)
        return buffer.getvalue()

    async def synthesize_wav_base64(self, text: str) -> str | None:
        text = text.strip()
        if not text:
            return None

        self._ensure_client()
        if self._client is None:
            return None

        prompt = self._build_prompt(text)
        try:
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=self.config.gemini_tts_model,
                contents=prompt,
                config={
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": self.config.gemini_tts_voice,
                            }
                        }
                    },
                },
            )
            pcm_bytes = self._extract_inline_audio_bytes(response)
            wav_bytes = self._pcm_to_wav_bytes(pcm_bytes)
            return base64.b64encode(wav_bytes).decode("ascii")
        except Exception as exc:
            self.logger.warning("Gemini TTS synthesis failed. Falling back to text-only ack: %s", exc)
            return None
