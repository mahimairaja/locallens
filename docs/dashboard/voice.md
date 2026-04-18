# Dashboard: Voice

Voice features are integrated directly into the [Ask page](/dashboard/ask).

## Speech-to-text (input)

Click the mic button next to the send button to record your question. The audio is sent to the backend for transcription via Moonshine STT, then automatically submitted.

## Text-to-speech (output)

Each assistant message has a small speaker button. Click it to hear the answer read aloud via Piper TTS.

## Requirements

```bash
pip install "locallens[voice]"
```

You also need `ffmpeg` on your PATH for audio decoding.
