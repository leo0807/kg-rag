"""
Whisper Large-v3 speech-to-text service for workshop environments.

Local deployment preferred (no network dependency on shop floor).
Falls back to OpenAI Whisper API if local model not loaded.

Features:
- Audio preprocessing: resampling to 16 kHz mono
- Language hint: "zh" for Chinese engineering terminology
- Special command detection: "打开 CPS1220 第三章" → nav intent
"""
from __future__ import annotations

import io
import logging
import os
import re
from typing import Any

log = logging.getLogger(__name__)

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
WHISPER_DEVICE     = os.getenv("WHISPER_DEVICE", "cpu")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")

# Special command patterns → action intents
_CMD_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"打开\s*(.+?)\s*第(.+?)章"), "open_chapter", "doc,chapter"),
    (re.compile(r"显示\s*(.+?)\s*图谱"),       "show_graph",   "topic"),
    (re.compile(r"搜索\s*(.+)"),                "search",       "query"),
    (re.compile(r"返回\s*首页"),                "navigate",     "home"),
    (re.compile(r"显示\s*工艺\s*步骤"),         "show_steps",   ""),
]

_CHINESE_NUMBER = {
    "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
    "十一": "11", "十二": "12",
}


def _normalize_number(s: str) -> str:
    return _CHINESE_NUMBER.get(s, s)


def detect_command(text: str) -> dict | None:
    """
    Parse transcribed text for navigation / action intents.
    Returns None if no command is detected.
    """
    for pattern, action, arg_spec in _CMD_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        groups = m.groups()
        if action == "open_chapter" and len(groups) >= 2:
            return {
                "action":  action,
                "doc_id":  groups[0].strip(),
                "chapter": _normalize_number(groups[1].strip()),
            }
        if action == "show_graph" and groups:
            return {"action": action, "topic": groups[0].strip()}
        if action == "search" and groups:
            return {"action": action, "query": groups[0].strip()}
        return {"action": action}
    return None


class WhisperSTT:
    """
    Local Whisper STT with optional OpenAI API fallback.
    Lazy-loads the model on first call to avoid startup latency.
    """

    def __init__(self):
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            import whisper
            log.info("Loading Whisper %s on %s", WHISPER_MODEL_SIZE, WHISPER_DEVICE)
            self._model = whisper.load_model(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE)
        except ImportError:
            log.warning("openai-whisper not installed; will use OpenAI API fallback")

    def _preprocess(self, audio_bytes: bytes) -> "np.ndarray":
        """Resample to 16 kHz mono float32 for Whisper."""
        import numpy as np
        try:
            import librosa
            audio, _ = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
        except ImportError:
            # Minimal fallback: assume PCM16 at 16 kHz
            data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            audio = data
        return audio

    def transcribe_local(self, audio_bytes: bytes, language: str = "zh") -> str:
        self._load_model()
        if self._model is None:
            raise RuntimeError("Local model not available")
        audio = self._preprocess(audio_bytes)
        result = self._model.transcribe(
            audio,
            language=language,
            task="transcribe",
            fp16=(WHISPER_DEVICE != "cpu"),
            initial_prompt="以下是一段工艺规范讨论的录音，涉及液压、力矩、航空制造等专业术语。",
        )
        return result.get("text", "").strip()

    def transcribe_api(self, audio_bytes: bytes, language: str = "zh") -> str:
        """OpenAI Whisper API fallback."""
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set")
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", io.BytesIO(audio_bytes), "audio/wav"),
            language=language,
            prompt="工艺规范 液压 力矩 航空 CPS",
        )
        return response.text.strip()

    def transcribe(self, audio_bytes: bytes, language: str = "zh") -> dict:
        """
        Transcribe audio. Returns {text, command?, language}.
        Tries local model first, falls back to API.
        """
        try:
            text = self.transcribe_local(audio_bytes, language)
        except Exception as local_err:
            log.info("Local transcription failed (%s); using API", local_err)
            text = self.transcribe_api(audio_bytes, language)

        command = detect_command(text)
        return {"text": text, "command": command, "language": language}


_stt_instance: WhisperSTT | None = None


def get_stt() -> WhisperSTT:
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = WhisperSTT()
    return _stt_instance
