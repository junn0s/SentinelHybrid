#!/usr/bin/env python3
from __future__ import annotations

import base64
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import wave


DEFAULT_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Kore"
DEFAULT_RATE_HZ = 24000
DEFAULT_CHANNELS = 1
DEFAULT_SAMPLE_WIDTH = 2
DEFAULT_PLAYER = "ffplay -nodisp -autoexit"


def _first_set(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _read_text(argv: list[str]) -> str:
    if len(argv) > 1:
        return " ".join(argv[1:]).strip()
    return sys.stdin.read().strip()


def _extract_audio_bytes(response: object) -> bytes:
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
                try:
                    return base64.b64decode(data)
                except Exception as exc:
                    raise RuntimeError(f"inline_data decode failed: {exc}") from exc
    raise RuntimeError("Gemini TTS returned no inline audio data")


def _save_wav(path: Path, pcm_data: bytes) -> None:
    channels = int((os.getenv("GEMINI_TTS_CHANNELS") or str(DEFAULT_CHANNELS)).strip() or str(DEFAULT_CHANNELS))
    rate_hz = int((os.getenv("GEMINI_TTS_RATE_HZ") or str(DEFAULT_RATE_HZ)).strip() or str(DEFAULT_RATE_HZ))
    sample_width = int((os.getenv("GEMINI_TTS_SAMPLE_WIDTH") or str(DEFAULT_SAMPLE_WIDTH)).strip() or str(DEFAULT_SAMPLE_WIDTH))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate_hz)
        wf.writeframes(pcm_data)


def _play_audio(path: Path) -> None:
    player_raw = (os.getenv("GEMINI_TTS_PLAYER") or DEFAULT_PLAYER).strip() or DEFAULT_PLAYER
    player_cmd = shlex.split(player_raw)
    if not player_cmd:
        raise RuntimeError("GEMINI_TTS_PLAYER is empty")
    if shutil.which(player_cmd[0]) is None:
        raise RuntimeError(f"Audio player not found: {player_cmd[0]}")

    timeout_sec = float((os.getenv("GEMINI_TTS_PLAY_TIMEOUT_SEC") or "20").strip() or "20")
    completed = subprocess.run(
        [*player_cmd, str(path)],
        check=False,
        timeout=timeout_sec,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Audio player returned non-zero code={completed.returncode}")


def _build_prompt(text: str) -> str:
    style = (os.getenv("GEMINI_TTS_STYLE_PROMPT") or "").strip()
    if style:
        return f"{style}\n\n{text}"
    return text


def main() -> int:
    text = _read_text(sys.argv)
    if not text:
        print("No TTS text provided", file=sys.stderr)
        return 2

    api_key = _first_set("GOOGLE_API_KEY", "GEMINI_API_KEY")
    if not api_key:
        print("Gemini TTS failed: GOOGLE_API_KEY (or GEMINI_API_KEY) is not set", file=sys.stderr)
        return 1

    model = (os.getenv("GEMINI_TTS_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    voice = (os.getenv("GEMINI_TTS_VOICE") or DEFAULT_VOICE).strip() or DEFAULT_VOICE
    prompt = _build_prompt(text)

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        print(f"Gemini TTS failed: google-genai import error: {exc}", file=sys.stderr)
        return 1

    with tempfile.NamedTemporaryFile(prefix="gemini_tts_", suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )
        audio_bytes = _extract_audio_bytes(response)
        _save_wav(wav_path, audio_bytes)
        _play_audio(wav_path)
        return 0
    except Exception as exc:
        print(f"Gemini TTS failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
