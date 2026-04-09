from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from app.models import TranscribeResponse, SynthesizeRequest
from app.services import voice_stt, voice_tts
from app.services.rag import stream_answer
import json

router = APIRouter()


@router.post("/voice/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    if not voice_stt.is_available():
        raise HTTPException(501, "STT not available. Install: pip install 'locallens[voice]'")

    audio_bytes = await file.read()
    text, duration_ms = voice_stt.transcribe(audio_bytes)
    return TranscribeResponse(text=text, duration_ms=duration_ms)


@router.post("/voice/synthesize")
async def synthesize(req: SynthesizeRequest):
    if not voice_tts.is_available():
        raise HTTPException(501, "TTS not available. Install: pip install 'locallens[voice]'")

    wav_bytes = voice_tts.synthesize(req.text)
    return Response(content=wav_bytes, media_type="audio/wav")


@router.post("/voice/conversation")
async def voice_conversation(file: UploadFile = File(...)):
    if not voice_stt.is_available():
        raise HTTPException(501, "STT not available. Install: pip install 'locallens[voice]'")

    # Transcribe
    audio_bytes = await file.read()
    text, stt_ms = voice_stt.transcribe(audio_bytes)

    # Determine intent
    search_keywords = ["search for", "find", "look for", "where is", "locate"]
    intent = "ask"
    for kw in search_keywords:
        if kw in text.lower():
            intent = "search"
            break

    # Execute
    response_text = ""
    sources = []
    for token, srcs in stream_answer(text, top_k=3):
        if token is not None:
            response_text += token
        if srcs is not None:
            sources = [s.model_dump() for s in srcs]

    # Synthesize response if TTS available
    audio_base64 = None
    if voice_tts.is_available():
        import base64
        wav_bytes = voice_tts.synthesize(response_text[:500])  # Limit TTS length
        audio_base64 = base64.b64encode(wav_bytes).decode()

    return {
        "transcription": text,
        "intent": intent,
        "response_text": response_text,
        "audio_base64": audio_base64,
        "sources": sources,
    }


@router.get("/voice/status")
async def voice_status():
    return {
        "stt_available": voice_stt.is_available(),
        "tts_available": voice_tts.is_available(),
    }
