"""
Text-to-speech service for workshop voice output.

Priority chain:
1. CosyVoice (local, Chinese-native, industrial vocabulary)
2. ChatTTS   (local, expressive Mandarin)
3. edge-tts  (Microsoft, free, no auth required)
4. pyttsx3   (offline OS TTS, last resort)
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Literal

log = logging.getLogger(__name__)

TTS_ENGINE   = os.getenv("TTS_ENGINE", "auto")   # cosyvoice | chattts | edge | pyttsx3 | auto
TTS_VOICE    = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
COSYVOICE_URL = os.getenv("COSYVOICE_URL", "http://localhost:9880")


AudioFormat = Literal["mp3", "wav", "ogg"]


async def _tts_cosyvoice(text: str, voice: str = "default") -> bytes:
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{COSYVOICE_URL}/v1/audio/speech",
            json={"input": text, "voice": voice, "response_format": "wav"},
        )
    r.raise_for_status()
    return r.content


async def _tts_chattts(text: str) -> bytes:
    """ChatTTS local HTTP API (default port 9881)."""
    import httpx
    chattts_url = os.getenv("CHATTTS_URL", "http://localhost:9881")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{chattts_url}/tts", json={"text": text})
    r.raise_for_status()
    return r.content


async def _tts_edge(text: str, voice: str = "zh-CN-XiaoxiaoNeural") -> bytes:
    """Microsoft edge-tts — free, no API key, requires edge-tts pip package."""
    import edge_tts
    buf = io.BytesIO()
    communicate = edge_tts.Communicate(text, voice)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def _tts_pyttsx3(text: str) -> bytes:
    """pyttsx3 fallback — synchronous, offline OS TTS."""
    import pyttsx3
    import tempfile, wave
    engine = pyttsx3.init()
    # Set Chinese voice if available
    for voice in engine.getProperty("voices"):
        if "zh" in voice.id.lower() or "chinese" in voice.name.lower():
            engine.setProperty("voice", voice.id)
            break
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    engine.save_to_file(text, path)
    engine.runAndWait()
    with open(path, "rb") as f:
        return f.read()


async def synthesize(
    text: str,
    engine: str = TTS_ENGINE,
    voice: str = TTS_VOICE,
    fmt: AudioFormat = "mp3",
) -> bytes:
    """
    Convert text to speech. Returns raw audio bytes in the requested format.
    Engine selection order: cosyvoice → chattts → edge → pyttsx3.
    """
    if len(text) > 500:
        text = text[:497] + "..."

    engines = (
        [engine] if engine != "auto"
        else ["cosyvoice", "chattts", "edge", "pyttsx3"]
    )

    for eng in engines:
        try:
            if eng == "cosyvoice":
                return await _tts_cosyvoice(text, voice)
            elif eng == "chattts":
                return await _tts_chattts(text)
            elif eng == "edge":
                return await _tts_edge(text, voice)
            elif eng == "pyttsx3":
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, _tts_pyttsx3, text)
        except Exception as exc:
            log.debug("TTS engine %s failed: %s", eng, exc)
            continue

    raise RuntimeError("All TTS engines failed")


def get_available_engines() -> list[str]:
    """Return list of TTS engines that are currently available."""
    available = []
    try:
        import httpx
        import requests
        r = requests.get(f"{COSYVOICE_URL}/health", timeout=2)
        if r.ok:
            available.append("cosyvoice")
    except Exception:
        pass
    try:
        import edge_tts  # noqa: F401
        available.append("edge")
    except ImportError:
        pass
    try:
        import pyttsx3  # noqa: F401
        available.append("pyttsx3")
    except ImportError:
        pass
    return available
