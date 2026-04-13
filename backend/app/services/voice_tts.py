"""Text-to-speech via moonshine-voice's bundled TextToSpeech.

This avoids the separate kokoro-onnx model files (kokoro-v0_19.onnx +
voices.json) that used to be required — moonshine-voice downloads its
own assets on first use and then caches them locally.
"""

import io
import logging
import wave

logger = logging.getLogger(__name__)

_tts_model = None
_tts_available = False


def is_available() -> bool:
    return _tts_available


def load_model():
    global _tts_model, _tts_available
    try:
        from moonshine_voice import TextToSpeech

        # Assets download on first call if missing; cached afterwards.
        _tts_model = TextToSpeech(language="en-us", download=True)
        _tts_available = True
        logger.info("Moonshine TTS model loaded (en-us)")
    except ImportError:
        logger.warning("moonshine-voice not installed. Voice TTS unavailable.")
        _tts_available = False
    except Exception as e:
        logger.warning(f"Failed to load TTS: {e}")
        _tts_available = False


def synthesize(text: str, voice: str | None = None) -> bytes:
    """Synthesize text to WAV bytes (mono int16)."""
    if not _tts_available or _tts_model is None:
        raise RuntimeError("TTS model not loaded.")

    import numpy as np

    samples, sample_rate = _tts_model.synthesize(text)
    arr = np.asarray(samples, dtype=np.float32)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        audio_int16 = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()
