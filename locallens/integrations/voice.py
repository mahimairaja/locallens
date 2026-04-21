"""Voice loop: mic -> STT -> intent -> search/ask -> TTS -> speaker."""

from rich.console import Console

from locallens.config import (
    DEFAULT_TOP_K,
    KOKORO_SPEED,
    KOKORO_VOICE,
    RAG_TOP_K,
    SAMPLE_RATE,
)

console = Console()

# Intent keywords
_SEARCH_KEYWORDS = ("search for", "find", "look for", "where is")
_EXIT_KEYWORDS = ("quit", "exit", "stop", "goodbye")


def _classify_intent(text: str) -> str:
    """Classify user intent from transcribed text."""
    lower = text.lower()
    for kw in _EXIT_KEYWORDS:
        if kw in lower:
            return "exit"
    for kw in _SEARCH_KEYWORDS:
        if kw in lower:
            return "search"
    return "ask"


def start_voice_loop(store, embed_query_fn) -> None:
    """Main voice loop entry point."""
    # Check voice dependencies first
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        console.print(
            "[red]Voice dependencies not installed.[/red]\n"
            "Install them with: [bold]pip install locallens\\[voice][/bold]"
        )
        return

    try:
        from moonshine_voice import MoonshineModel
    except ImportError:
        console.print(
            "[red]Moonshine STT not installed.[/red]\n"
            "Install with: [bold]pip install moonshine-voice[/bold]"
        )
        return

    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        console.print(
            "[red]Kokoro TTS not installed.[/red]\n"
            "Install with: [bold]pip install kokoro-onnx[/bold]"
        )
        return

    # Check Ollama
    import httpx

    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        console.print(
            "[red]Error: Ollama is not running. Start it with: ollama serve[/red]\n"
            "[red]Then pull the model: ollama pull qwen2.5:3b[/red]"
        )
        return

    console.print(
        "[bold green]LocalLens Voice Mode[/bold green] — speak to search your files. "
        "Say 'quit' or 'exit' to stop.\n"
    )

    # Load models
    with console.status("Loading models..."):
        try:
            stt_model = MoonshineModel()
        except Exception as exc:
            console.print(f"[red]Failed to load Moonshine STT: {exc}[/red]")
            return

        try:
            tts_model = Kokoro()
        except Exception as exc:
            console.print(f"[red]Failed to load Kokoro TTS: {exc}[/red]")
            return

    console.print("[green]Models loaded. Listening...[/green]\n")

    from locallens.pipeline.rag import ask as do_ask
    from locallens.pipeline.searcher import search as do_search

    try:
        while True:
            # Record audio until silence
            try:
                console.print("[dim]Listening... (speak now)[/dim]")
                audio_chunks: list[np.ndarray] = []
                silence_frames = 0
                max_record = int(SAMPLE_RATE * 30)  # 30s max

                def callback(indata, frames, time_info, status):
                    audio_chunks.append(indata.copy())

                with sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=1024,
                    callback=callback,
                ):
                    import time

                    total_frames = 0
                    while total_frames < max_record:
                        time.sleep(0.1)
                        total_frames = sum(c.shape[0] for c in audio_chunks)
                        if total_frames > SAMPLE_RATE * 2:  # At least 2 seconds
                            # Check for silence at end
                            if len(audio_chunks) > 0:
                                recent = np.concatenate(audio_chunks[-15:])
                                energy = np.abs(recent).mean()
                                if energy < 0.005:
                                    silence_frames += 1
                                    if silence_frames > 10:
                                        break
                                else:
                                    silence_frames = 0

                if not audio_chunks:
                    continue

                audio = np.concatenate(audio_chunks).flatten()

            except sd.PortAudioError as exc:
                console.print(
                    f"[red]Microphone error: {exc}[/red]\n"
                    "Make sure a microphone is connected and permissions are granted."
                )
                return

            # Transcribe
            try:
                transcription = stt_model.transcribe(audio)
                if not transcription or not transcription.strip():
                    continue
            except Exception as exc:
                console.print(f"[yellow]Transcription error: {exc}[/yellow]")
                continue

            console.print(f'[bold]You:[/bold] "{transcription}"')

            # Classify intent
            intent = _classify_intent(transcription)

            if intent == "exit":
                console.print("[bold green]Goodbye![/bold green]")
                break

            if intent == "search":
                results = do_search(transcription, DEFAULT_TOP_K)
                if results:
                    top = results[0]
                    fn = top.payload.get("file_name", "unknown")
                    preview = top.payload.get("chunk_text", "")[:50]
                    response = (
                        f"I found {len(results)} results. "
                        f"The top match is {fn}, which contains content about {preview}."
                    )
                else:
                    response = "I didn't find any matching files."

                console.print(f'[bold cyan]LocalLens:[/bold cyan] "{response}"')

            else:  # ask mode
                response_parts: list[str] = []
                for token in do_ask(transcription, store, top_k=RAG_TOP_K):
                    response_parts.append(token)
                response = "".join(response_parts).strip()
                console.print(f'[bold cyan]LocalLens:[/bold cyan] "{response}"')

            # TTS
            tts_text = response
            if len(tts_text) > 200:
                tts_text = (
                    tts_text[:197] + "... Check the terminal for the full answer."
                )

            try:
                audio_out, sr = tts_model.create(
                    tts_text, voice=KOKORO_VOICE, speed=KOKORO_SPEED
                )
                sd.play(audio_out, samplerate=sr)
                sd.wait()
            except Exception as exc:
                console.print(f"[yellow]TTS playback error: {exc}[/yellow]")

    except KeyboardInterrupt:
        console.print("\n[bold green]Goodbye![/bold green]")
