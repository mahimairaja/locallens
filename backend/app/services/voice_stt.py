"""Speech-to-text via moonshine-voice.

Uses the bundled ``tiny-en`` model (shipped inside the package assets, no
external download required). Incoming audio bytes from the browser's
MediaRecorder are webm/opus, so we transcode them to 16 kHz mono PCM
floats via ffmpeg before feeding them to the Transcriber.
"""

import logging
import shutil
import subprocess
import time

logger = logging.getLogger(__name__)

_stt_model = None
_stt_available = False


def is_available() -> bool:
    return _stt_available


def load_model():
    global _stt_model, _stt_available
    try:
        from moonshine_voice import ModelArch, Transcriber, get_model_path

        model_path = get_model_path("tiny-en")
        if not model_path.exists():
            logger.warning("Moonshine tiny-en assets missing at %s", model_path)
            _stt_available = False
            return

        _stt_model = Transcriber(str(model_path), ModelArch.TINY)
        _stt_available = True
        logger.info("Moonshine STT model loaded (tiny-en)")
    except ImportError:
        logger.warning("moonshine-voice not installed. Voice STT unavailable.")
        _stt_available = False
    except Exception as e:
        logger.warning(f"Failed to load Moonshine: {e}")
        _stt_available = False


def _decode_to_pcm_floats(audio_bytes: bytes, target_rate: int = 16000) -> list[float]:
    """Transcode arbitrary audio (webm, wav, mp3, …) to mono 16 kHz PCM floats.

    Uses the system ffmpeg binary. Output is a list of float samples in -1..1.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH — install it (e.g. `brew install ffmpeg`) "
            "so the backend can decode browser audio for STT."
        )

    import numpy as np

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            str(target_rate),
            "pipe:1",
        ],
        input=audio_bytes,
        capture_output=True,
        check=True,
    )
    pcm_int16 = np.frombuffer(proc.stdout, dtype=np.int16)
    return list((pcm_int16.astype(np.float32) / 32768.0).tolist())


def transcribe(audio_bytes: bytes, sample_rate: int = 16000) -> tuple[str, float]:
    """Transcribe audio bytes to text. Returns (text, duration_ms)."""
    if not _stt_available or _stt_model is None:
        raise RuntimeError("STT model not loaded. Install moonshine-voice.")

    start = time.time()
    samples = _decode_to_pcm_floats(audio_bytes, target_rate=sample_rate)
    transcript = _stt_model.transcribe_without_streaming(
        samples, sample_rate=sample_rate
    )

    # Transcript object has .lines (list of TranscriptLine with .text)
    if hasattr(transcript, "lines") and transcript.lines:
        text = " ".join(
            line.text for line in transcript.lines if getattr(line, "text", None)
        )
    else:
        text = str(transcript)

    duration_ms = (time.time() - start) * 1000
    return text.strip(), duration_ms
