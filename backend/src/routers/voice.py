"""
Voice interface endpoints for hands-free workshop operation.

POST /api/voice/transcribe    — Upload audio → text + optional nav command
POST /api/voice/synthesize    — Text → audio bytes (MP3/WAV)
POST /api/voice/query         — Full pipeline: audio → answer text + audio
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ..auth.deps import get_current_user
from ..db.models import User
from ..services.voice.whisper_stt import get_stt
from ..services.voice.tts_service import get_available_engines, synthesize

import httpx, os

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])

BACKEND_URL     = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
_HEADERS        = {"X-API-Key": BACKEND_API_KEY} if BACKEND_API_KEY else {}


class SynthesizeRequest(BaseModel):
    text:   str
    voice:  str = "zh-CN-XiaoxiaoNeural"
    engine: str = "auto"
    fmt:    str = "mp3"


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(..., description="WAV/MP3/OGG audio file"),
    language: str = Form(default="zh"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Transcribe audio to text using Whisper Large-v3.

    Returns:
    - text:    transcribed text
    - command: parsed navigation/action intent (if any)
    - language: detected/requested language
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        stt    = get_stt()
        result = stt.transcribe(audio_bytes, language=language)
    except Exception as exc:
        log.error("STT failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")

    return result


@router.post("/synthesize")
async def synthesize_audio(
    body: SynthesizeRequest,
    _: User = Depends(get_current_user),
) -> Response:
    """
    Convert text to speech.

    Returns audio bytes with Content-Type audio/mpeg or audio/wav.
    """
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    try:
        audio_bytes = await synthesize(body.text, body.engine, body.voice, body.fmt)  # type: ignore[arg-type]
    except Exception as exc:
        log.error("TTS failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"TTS failed: {exc}")

    content_type = "audio/mpeg" if body.fmt == "mp3" else "audio/wav"
    return Response(content=audio_bytes, media_type=content_type)


@router.post("/query")
async def voice_query(
    audio: UploadFile = File(..., description="Audio file containing the question"),
    language: str      = Form(default="zh"),
    strategy: str      = Form(default="graph_augmented"),
    tts_engine: str    = Form(default="auto"),
    _: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Full voice pipeline:
    1. Transcribe audio → text
    2. Detect navigation commands (if any, return immediately)
    3. Run question through the knowledge-base query pipeline
    4. Synthesize the answer as audio
    5. Return: {text, answer, audio_base64, command?}
    """
    import base64

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Step 1: STT
    stt    = get_stt()
    stt_result = stt.transcribe(audio_bytes, language=language)
    text   = stt_result["text"]
    command = stt_result.get("command")

    # Step 2: Navigation command — return without querying KB
    if command:
        try:
            tts_bytes = await synthesize(
                f"好的，正在{text}。", engine=tts_engine
            )
            audio_b64 = base64.b64encode(tts_bytes).decode()
        except Exception:
            audio_b64 = ""
        return {
            "text":         text,
            "command":      command,
            "answer":       None,
            "audio_base64": audio_b64,
        }

    # Step 3: Knowledge-base query
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{BACKEND_URL}/api/query",
                json={"question": text, "strategy": strategy, "top_k": 3},
                headers=_HEADERS,
            )
        answer = r.json().get("answer", "抱歉，未找到相关内容。")
    except Exception as exc:
        answer = f"查询失败：{exc}"

    # Step 4: TTS
    try:
        tts_bytes = await synthesize(answer, engine=tts_engine)
        audio_b64 = base64.b64encode(tts_bytes).decode()
    except Exception:
        audio_b64 = ""

    return {
        "text":         text,
        "command":      None,
        "answer":       answer,
        "audio_base64": audio_b64,
    }


@router.get("/engines")
async def list_tts_engines(_: User = Depends(get_current_user)) -> dict:
    """List available TTS engines on this server."""
    return {"engines": get_available_engines()}
