import logging
import time

logger = logging.getLogger(__name__)

_stt_model = None
_stt_available = False


def is_available() -> bool:
    return _stt_available


def load_model():
    global _stt_model, _stt_available
    try:
        from moonshine_voice import Moonshine
        _stt_model = Moonshine(model_name="moonshine/base")
        _stt_available = True
        logger.info("Moonshine STT model loaded")
    except ImportError:
        logger.warning("moonshine-voice not installed. Voice STT unavailable.")
        _stt_available = False
    except Exception as e:
        logger.warning(f"Failed to load Moonshine: {e}")
        _stt_available = False


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> tuple[str, float]:
    """Transcribe audio bytes to text. Returns (text, duration_ms)."""
    if not _stt_available or _stt_model is None:
        raise RuntimeError("STT model not loaded. Install moonshine-voice.")

    import numpy as np
    start = time.time()
    audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    text = _stt_model.transcribe(audio, sample_rate=sample_rate)
    if isinstance(text, list):
        text = " ".join(text)
    duration_ms = (time.time() - start) * 1000
    return text.strip(), duration_ms
