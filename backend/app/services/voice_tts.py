import logging
import io
import wave
import struct

logger = logging.getLogger(__name__)

_tts_model = None
_tts_available = False


def is_available() -> bool:
    return _tts_available


def load_model():
    global _tts_model, _tts_available
    try:
        from kokoro_onnx import Kokoro
        _tts_model = Kokoro("kokoro-v0_19.onnx", "voices.json")
        _tts_available = True
        logger.info("Kokoro TTS model loaded")
    except ImportError:
        logger.warning("kokoro-onnx not installed. Voice TTS unavailable.")
        _tts_available = False
    except Exception as e:
        logger.warning(f"Failed to load Kokoro: {e}")
        _tts_available = False


def synthesize(text: str, voice: str = "af_heart") -> bytes:
    """Synthesize text to WAV bytes."""
    if not _tts_available or _tts_model is None:
        raise RuntimeError("TTS model not loaded. Install kokoro-onnx.")

    import numpy as np
    samples, sample_rate = _tts_model.create(text, voice=voice, speed=1.0)

    # Convert to WAV bytes
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        audio_int16 = (samples * 32767).astype(np.int16)
        wf.writeframes(audio_int16.tobytes())
    return buf.getvalue()
