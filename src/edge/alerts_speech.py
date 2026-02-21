import logging
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile


class SpeechOutput:
    def __init__(
        self,
        simulate_only: bool = True,
        tts_enabled: bool = True,
        tts_command: str | None = None,
        tts_piper_model: str | None = None,
        tts_piper_speaker_id: int | None = None,
        tts_timeout_sec: int = 8,
        logger: logging.Logger | None = None,
    ) -> None:
        self.simulate_only = simulate_only
        self.tts_enabled = tts_enabled
        self.tts_piper_model = tts_piper_model
        self.tts_piper_speaker_id = tts_piper_speaker_id
        self.tts_timeout_sec = tts_timeout_sec
        self.logger = logger or logging.getLogger(__name__)
        self._tts_cmd = self._resolve_tts_command(tts_command)

    def _resolve_tts_command(self, tts_command: str | None) -> list[str] | None:
        if not self.tts_enabled:
            return None

        if tts_command:
            tokens = shlex.split(tts_command)
            if tokens and shutil.which(tokens[0]):
                return tokens
            self.logger.warning("Configured TTS command unavailable: %s", tts_command)

        # Prefer local neural TTS via Piper when model path + runtime are available.
        if self._can_use_piper():
            return ["piper"]

        for candidate in ("espeak-ng", "espeak", "spd-say", "say"):
            if shutil.which(candidate):
                return [candidate]
        self.logger.warning("No local TTS binary found. Tried piper+ffplay/espeak-ng/espeak/spd-say/say.")
        return None

    def speak(self, text: str) -> None:
        if not self.tts_enabled:
            return

        text = text.strip()
        if not text:
            return

        if self.simulate_only:
            self.logger.warning("[SIM] TTS: %s", text)
            return

        if not self._tts_cmd:
            self.logger.warning("TTS skipped: command not configured or unavailable.")
            return

        try:
            if self._tts_cmd[0] == "piper":
                self._speak_with_piper(text)
                return

            if any("{text}" in token for token in self._tts_cmd):
                cmd = [token.replace("{text}", text) for token in self._tts_cmd]
            else:
                cmd = [*self._tts_cmd, text]

            completed = subprocess.run(
                cmd,
                timeout=self.tts_timeout_sec,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                details = (completed.stderr or completed.stdout or "").strip()
                if details:
                    details = " ".join(details.split())[:240]
                    self.logger.warning(
                        "TTS command returned non-zero code=%s detail=%s",
                        completed.returncode,
                        details,
                    )
                else:
                    self.logger.warning("TTS command returned non-zero code=%s", completed.returncode)
        except subprocess.TimeoutExpired:
            self.logger.warning("TTS command timed out after %ss", self.tts_timeout_sec)
        except Exception as exc:
            self.logger.warning("TTS playback failed: %s", exc)

    def play_wav_bytes(self, wav_bytes: bytes) -> bool:
        if not self.tts_enabled:
            return False
        if not wav_bytes:
            return False
        if self.simulate_only:
            self.logger.warning("[SIM] TTS WAV received. bytes=%s", len(wav_bytes))
            return True
        if not shutil.which("ffplay"):
            self.logger.warning("ffplay not installed. Cannot play server WAV audio.")
            return False

        audio_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="server_tts_", suffix=".wav", delete=False) as tmp:
                audio_path = tmp.name
                tmp.write(wav_bytes)

            play_run = subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", audio_path],
                timeout=max(20, self.tts_timeout_sec + 12),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if play_run.returncode != 0:
                self.logger.warning("ffplay returned non-zero code=%s while playing server WAV", play_run.returncode)
                return False
            return True
        except Exception as exc:
            self.logger.warning("Server WAV playback failed: %s", exc)
            return False
        finally:
            if audio_path:
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _can_use_piper(self) -> bool:
        if not shutil.which("piper"):
            return False
        if not shutil.which("ffplay"):
            self.logger.warning("ffplay not installed. Piper output playback unavailable.")
            return False
        if not self.tts_piper_model:
            self.logger.warning("Piper model path not set. Set EDGE_TTS_PIPER_MODEL to use local neural TTS.")
            return False
        model_path = Path(self.tts_piper_model)
        if not model_path.exists():
            self.logger.warning("Piper model not found: %s", model_path)
            return False
        return True

    def _speak_with_piper(self, text: str) -> None:
        if not shutil.which("piper"):
            self.logger.warning("piper not installed. Skipping neural TTS path.")
            return

        if not shutil.which("ffplay"):
            self.logger.warning("ffplay not installed. Cannot play piper audio output.")
            return

        if not self.tts_piper_model:
            self.logger.warning("Piper model path is empty. Set EDGE_TTS_PIPER_MODEL.")
            return

        model_path = Path(self.tts_piper_model)
        if not model_path.exists():
            self.logger.warning("Piper model not found: %s", model_path)
            return

        audio_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="piper_tts_", suffix=".wav", delete=False) as tmp:
                audio_path = tmp.name

            tts_cmd = [
                "piper",
                "--model",
                str(model_path),
                "--output_file",
                audio_path,
            ]
            if self.tts_piper_speaker_id is not None:
                tts_cmd.extend(["--speaker", str(self.tts_piper_speaker_id)])
            tts_run = subprocess.run(
                tts_cmd,
                input=text,
                text=True,
                timeout=self.tts_timeout_sec,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if tts_run.returncode != 0:
                self.logger.warning("piper returned non-zero code=%s", tts_run.returncode)
                return

            play_cmd = ["ffplay", "-nodisp", "-autoexit", audio_path]
            play_run = subprocess.run(
                play_cmd,
                timeout=self.tts_timeout_sec + 5,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if play_run.returncode != 0:
                self.logger.warning("ffplay returned non-zero code=%s while playing piper output", play_run.returncode)
        except Exception as exc:
            self.logger.warning("piper playback failed: %s", exc)
        finally:
            if audio_path:
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass
