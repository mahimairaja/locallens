# Dashboard: Ask

The Ask page provides a chat-like interface for RAG Q&A with voice support.

## Features

- Chat-style message interface
- Streaming answers (token by token via SSE)
- Source citations below each answer
- Mic button for voice input (requires `locallens[voice]`)
- Speaker button on each answer for TTS playback

## Requirements

- Ollama must be running for answers (`ollama serve`)
- Voice features require `pip install "locallens[voice]"` and `ffmpeg` on PATH
