"""Text-to-speech via Piper TTS (VITS-based, ONNX).

Piper is ~16x faster than Moonshine TTS on Apple Silicon for the same
text lengths, hitting ~2x real-time factor on the ``lessac-medium``
voice.  Model and config are auto-downloaded from HuggingFace on first
run and cached under ``~/.cache/locallens/piper/``.
"""

import io
import logging
import os
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

_tts_voice = None
_tts_available = False

# Model hosted on HuggingFace rhasspy/piper-voices
_VOICE_NAME = "en_US-lessac-medium"
_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"
_CACHE_DIR = Path(os.path.expanduser("~/.cache/locallens/piper"))


def _ensure_model_files() -> tuple[str, str]:
    """Download the ONNX model + JSON config if not already cached."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model_path = _CACHE_DIR / f"{_VOICE_NAME}.onnx"
    config_path = _CACHE_DIR / f"{_VOICE_NAME}.onnx.json"

    for filename, local in [
        (f"{_VOICE_NAME}.onnx", model_path),
        (f"{_VOICE_NAME}.onnx.json", config_path),
    ]:
        if local.exists():
            continue
        url = f"{_HF_BASE}/{filename}"
        logger.info("Downloading %s → %s", url, local)
        import httpx

        with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as resp:
            resp.raise_for_status()
            with open(local, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)

    return str(model_path), str(config_path)


def is_available() -> bool:
    return _tts_available


def load_model():
    global _tts_voice, _tts_available
    try:
        from piper import PiperVoice

        model_path, config_path = _ensure_model_files()
        _tts_voice = PiperVoice.load(model_path, config_path=config_path)
        _tts_available = True
        logger.info(
            "Piper TTS loaded (%s, %d Hz)",
            _VOICE_NAME,
            _tts_voice.config.sample_rate,
        )
    except ImportError:
        logger.warning("piper-tts not installed. Voice TTS unavailable.")
        _tts_available = False
    except Exception as e:
        logger.warning(f"Failed to load Piper TTS: {e}")
        _tts_available = False


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Synthesize text to WAV bytes (mono int16).

    The ``voice`` parameter is accepted for API compatibility but ignored —
    Piper uses the pre-loaded ``lessac-medium`` voice.
    """
    if not _tts_available or _tts_voice is None:
        raise RuntimeError("TTS model not loaded.")

    sample_rate = _tts_voice.config.sample_rate
    audio_bytes = b""
    for chunk in _tts_voice.synthesize(text):
        audio_bytes += chunk.audio_int16_bytes

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
    return buf.getvalue()
