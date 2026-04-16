"""Typer CLI for LocalLens: index, search, ask, voice, stats, doctor commands."""

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from locallens.config import COLLECTION_NAME, DEFAULT_TOP_K, QDRANT_PATH, RAG_TOP_K

app = typer.Typer(
    name="locallens",
    help="Search your files by talking to them -- 100% offline semantic search with voice.",
    no_args_is_help=True,
)
console = Console()

sync_app = typer.Typer(
    name="sync",
    help="Sync the local Qdrant Edge shard with a remote Qdrant server.",
    no_args_is_help=True,
)
app.add_typer(sync_app)


def _collection_for_namespace(namespace: str) -> str:
    """Return the Qdrant collection name for a given namespace.

    The default namespace maps to the original ``locallens`` collection.
    """
    if namespace == "default":
        return COLLECTION_NAME
    return f"locallens_{namespace}"


@sync_app.command("pull")
def sync_pull(
    incremental: bool = typer.Option(
        False,
        "--incremental",
        help="Only transfer segments that have changed since the last pull.",
    ),
) -> None:
    """Pull a shard snapshot from the remote Qdrant server into the local shard."""
    from locallens import sync

    try:
        if incremental:
            sync.pull_partial()
            console.print("[green]Partial snapshot applied.[/green]")
        else:
            sync.pull()
            console.print("[green]Full snapshot restored.[/green]")
    except Exception as exc:
        console.print(f"[red]Sync pull failed: {exc}[/red]")
        raise typer.Exit(code=1)


@sync_app.command("push")
def sync_push(
    namespace: str = typer.Option(
        "default", "--namespace", help="Namespace to operate on."
    ),
) -> None:
    """Push every locally indexed point to the remote Qdrant server."""
    from qdrant_edge import ScrollRequest

    from locallens import store as st
    from locallens import sync

    st.init()
    shard = st.get_shard()
    total = 0
    offset = None
    while True:
        points, next_offset = shard.scroll(
            ScrollRequest(limit=256, offset=offset, with_payload=True, with_vector=True)
        )
        batch = []
        for p in points:
            vec = None
            if isinstance(p.vector, dict):
                from locallens.config import VECTOR_NAME

                vec = p.vector.get(VECTOR_NAME)
            if vec is None:
                continue
            batch.append(
                {"id": str(p.id), "vector": list(vec), "payload": dict(p.payload or {})}  # type: ignore[arg-type]
            )
        if batch:
            total += sync.push(batch)
        if next_offset is None:
            break
        offset = next_offset
    console.print(f"[green]Pushed {total} points.[/green]")


@app.command()
def index(
    folder_path: Path = typer.Argument(..., help="Path to the folder to index."),
    force: bool = typer.Option(
        False, "--force", help="Re-index all files, ignoring hash cache."
    ),
    namespace: str = typer.Option(
        "default", "--namespace", help="Namespace to index into."
    ),
) -> None:
    """Index local files into the vector database for semantic search."""
    if not folder_path.is_dir():
        console.print(f"[red]Error: '{folder_path}' is not a valid directory.[/red]")
        raise typer.Exit(code=1)

    from locallens.indexer import index_folder

    index_folder(folder_path, force=force)


@app.command()
def search(
    query: str = typer.Argument(..., help="The search query."),
    top_k: int = typer.Option(
        DEFAULT_TOP_K, "--top-k", help="Number of results to return."
    ),
    file_type: str | None = typer.Option(
        None, "--file-type", help="Only return results for this extension, e.g. .pdf"
    ),
    path_prefix: str | None = typer.Option(
        None,
        "--path-prefix",
        help="Only return results whose file_path matches exactly.",
    ),
    namespace: str = typer.Option(
        "default", "--namespace", help="Namespace to search."
    ),
) -> None:
    """Semantic search over your indexed files."""
    from locallens import store as st
    from locallens.searcher import search as do_search

    st.init()
    if st.count() == 0:
        console.print(
            "[yellow]No files indexed yet. Run `locallens index <folder>` first.[/yellow]"
        )
        raise typer.Exit()

    results = do_search(query, top_k, file_type=file_type, path_prefix=path_prefix)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        raise typer.Exit()

    table = Table(title="Search Results")
    table.add_column("#", style="bold", width=4)
    table.add_column("Score", width=6)
    table.add_column("File", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Preview", max_width=60)

    for rank, hit in enumerate(results, 1):
        preview = hit.payload.get("chunk_text", "")[:200]
        if len(hit.payload.get("chunk_text", "")) > 200:
            preview += "..."
        table.add_row(
            str(rank),
            f"{hit.score:.2f}",
            hit.payload.get("file_name", ""),
            hit.payload.get("file_path", ""),
            preview,
        )

    console.print(table)


@app.command()
def ask(
    question: str = typer.Argument(..., help="The question to ask about your files."),
    top_k: int = typer.Option(
        RAG_TOP_K, "--top-k", help="Number of chunks to retrieve for context."
    ),
    namespace: str = typer.Option("default", "--namespace", help="Namespace to query."),
) -> None:
    """Ask a question about your indexed files using RAG."""
    from locallens import store as st
    from locallens.rag import ask as do_ask

    st.init()
    if st.count() == 0:
        console.print(
            "[yellow]No files indexed yet. Run `locallens index <folder>` first.[/yellow]"
        )
        raise typer.Exit()

    try:
        for token in do_ask(question, st, top_k=top_k):
            console.print(token, end="")
        console.print()
    except Exception as exc:
        error_msg = str(exc)
        if "Connection" in error_msg or "refused" in error_msg:
            console.print(
                "\n[red]Error: Ollama is not running. Start it with: ollama serve[/red]"
                "\n[red]Then pull the model: ollama pull qwen2.5:3b[/red]"
            )
        else:
            console.print(f"\n[red]Error: {exc}[/red]")
        raise typer.Exit(code=1)


@app.command()
def voice(
    namespace: str = typer.Option("default", "--namespace", help="Namespace to use."),
) -> None:
    """Start the voice interface -- speak to search your files."""
    try:
        from locallens.voice import start_voice_loop
    except ImportError:
        console.print(
            "[red]Voice dependencies not installed.[/red]\n"
            "Install them with: [bold]pip install locallens\\[voice][/bold]"
        )
        raise typer.Exit(code=1)

    from locallens import store as st
    from locallens.embedder import embed_query

    st.init()
    start_voice_loop(st, embed_query)


@app.command()
def watch(
    folder_path: Path = typer.Argument(..., help="Path to the folder to watch."),
    namespace: str = typer.Option("default", "--namespace", help="Namespace to use."),
) -> None:
    """Watch a folder for changes and re-index incrementally."""
    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        console.print(
            "[red]watchdog not installed.[/red]\n"
            "Install it with: [bold]pip install locallens\\[watch][/bold]"
        )
        raise typer.Exit(code=1)

    if not folder_path.is_dir():
        console.print(f"[red]Error: '{folder_path}' is not a valid directory.[/red]")
        raise typer.Exit(code=1)

    from locallens import store as st
    from locallens.config import SUPPORTED_EXTENSIONS

    st.init()

    class _CliWatchHandler(FileSystemEventHandler):
        def __init__(self):
            self.events = 0

        def on_created(self, event: FileSystemEvent):
            if event.is_directory:
                return
            self._handle(str(event.src_path), "created")

        def on_modified(self, event: FileSystemEvent):
            if event.is_directory:
                return
            self._handle(str(event.src_path), "modified")

        def on_deleted(self, event: FileSystemEvent):
            if event.is_directory:
                return
            abs_path = str(Path(str(event.src_path)).resolve())
            st.delete_by_file(abs_path)
            self.events += 1
            console.print(f"[red]Removed:[/red] {Path(str(event.src_path)).name}")

        def _handle(self, file_path: str, event_type: str):
            path = Path(file_path)
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                return
            if any(part.startswith(".") for part in path.parts):
                return
            if not path.is_file():
                return
            self.events += 1
            console.print(f"[cyan]{event_type}:[/cyan] {path.name} -- re-indexing...")
            try:
                from locallens.indexer import index_folder

                index_folder(path.parent, force=False)
            except Exception as exc:
                console.print(f"[yellow]Warning: reindex failed: {exc}[/yellow]")

    handler = _CliWatchHandler()
    observer = Observer()
    observer.schedule(handler, str(folder_path), recursive=True)
    observer.start()
    console.print(
        f"[green]Watching {folder_path} for changes. Press Ctrl+C to stop.[/green]"
    )

    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print(
            f"\n[green]Stopped watching. {handler.events} events processed.[/green]"
        )
    observer.join()


@app.command()
def stats(
    namespace: str = typer.Option(
        "default", "--namespace", help="Namespace to show stats for."
    ),
) -> None:
    """Show statistics about the indexed collection."""
    from locallens import store as st

    st.init()
    total_chunks = st.count()
    total_files = st.get_file_count()

    table = Table(title=f"LocalLens Stats (namespace: {namespace})")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total files indexed", str(total_files))
    table.add_row("Total chunks", str(total_chunks))
    table.add_row("Storage path", str(QDRANT_PATH))

    disk_usage = "N/A"
    if QDRANT_PATH.exists():
        total_bytes = sum(
            f.stat().st_size for f in QDRANT_PATH.rglob("*") if f.is_file()
        )
        if total_bytes < 1024 * 1024:
            disk_usage = f"{total_bytes / 1024:.1f} KB"
        else:
            disk_usage = f"{total_bytes / (1024 * 1024):.1f} MB"

    table.add_row("Disk usage", disk_usage)
    console.print(table)

    # File-type breakdown via Edge facet.
    file_types = st.facet_file_types(limit=20)
    if file_types:
        breakdown = Table(title="File type breakdown", show_edge=True)
        breakdown.add_column("Type", style="cyan")
        breakdown.add_column("Chunks", justify="right")
        for value, count in file_types:
            breakdown.add_row(value, str(count))
        console.print(breakdown)


@app.command()
def doctor() -> None:
    """Run health checks on all LocalLens dependencies."""
    import urllib.error
    import urllib.request

    from locallens.config import (
        EMBEDDING_MODEL,
        OLLAMA_BASE_URL,
        QDRANT_PATH,
    )

    PASS = "[green]\u2713[/green]"
    FAIL = "[red]\u2717[/red]"

    table = Table(title="LocalLens Doctor", show_edge=True)
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center", width=6)
    table.add_column("Detail")

    critical_ok = True

    # 1. Qdrant Edge (local shard)
    try:
        from locallens import store as st

        st.init()
        count = st.count()
        table.add_row("Qdrant Edge", PASS, f"Shard OK, {count} points at {QDRANT_PATH}")
    except Exception as exc:
        table.add_row("Qdrant Edge", FAIL, str(exc))
        critical_ok = False

    # 2. Qdrant Server (Docker HTTP)
    try:
        req = urllib.request.Request("http://localhost:6333/collections", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status < 400:
                table.add_row("Qdrant Server", PASS, "HTTP reachable at localhost:6333")
            else:
                table.add_row("Qdrant Server", FAIL, f"HTTP {resp.status}")
    except Exception:
        table.add_row(
            "Qdrant Server",
            "[yellow]-[/yellow]",
            "Not running (optional, needed for web app)",
        )

    # 3. Ollama
    try:
        req = urllib.request.Request(OLLAMA_BASE_URL, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status < 400:
                table.add_row("Ollama", PASS, f"Running at {OLLAMA_BASE_URL}")
            else:
                table.add_row("Ollama", FAIL, f"HTTP {resp.status}")
    except Exception:
        table.add_row(
            "Ollama", FAIL, f"Not reachable at {OLLAMA_BASE_URL} -- run: ollama serve"
        )

    # 4. Embedding model
    import contextlib
    import io
    import os
    import warnings

    try:
        # Silence the verbose model load report and progress bars.
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        with (
            warnings.catch_warnings(),
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            warnings.simplefilter("ignore")
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(EMBEDDING_MODEL)
            # Method renamed in newer versions; fall back for older installs.
            get_dim = getattr(
                _model,
                "get_embedding_dimension",
                getattr(_model, "get_sentence_embedding_dimension", lambda: None),
            )
            dim = get_dim()
        table.add_row("Embedding Model", PASS, f"{EMBEDDING_MODEL} ({dim}-dim)")
    except ImportError:
        table.add_row("Embedding Model", FAIL, "sentence-transformers not installed")
        critical_ok = False
    except Exception as exc:
        table.add_row("Embedding Model", FAIL, str(exc))
        critical_ok = False

    # 5. Voice STT
    try:
        from moonshine import Transcriber  # noqa: F401

        table.add_row("Voice STT", PASS, "moonshine-voice available")
    except ImportError:
        table.add_row(
            "Voice STT",
            "[yellow]-[/yellow]",
            "Not installed (optional): pip install locallens[voice]",
        )

    # 6. Voice TTS
    try:
        from piper import PiperVoice  # noqa: F401

        table.add_row("Voice TTS", PASS, "piper-tts available")
    except ImportError:
        table.add_row(
            "Voice TTS",
            "[yellow]-[/yellow]",
            "Not installed (optional): pip install locallens[voice]",
        )

    # 7. Disk space
    usage = shutil.disk_usage(Path.home())
    free_gb = usage.free / (1024**3)
    if free_gb < 1.0:
        table.add_row("Disk Space", FAIL, f"{free_gb:.1f} GB free (< 1 GB)")
    elif free_gb < 5.0:
        table.add_row(
            "Disk Space", "[yellow]![/yellow]", f"{free_gb:.1f} GB free (low)"
        )
    else:
        table.add_row("Disk Space", PASS, f"{free_gb:.1f} GB free")

    console.print()
    console.print(table)
    console.print()

    if critical_ok:
        console.print(
            Panel(
                "[green]All critical checks passed.[/green] Qdrant Edge and embedding model are working.",
                title="Result",
            )
        )
    else:
        console.print(
            Panel(
                "[red]Critical checks failed.[/red] Qdrant Edge and/or embedding model need attention.",
                title="Result",
            )
        )
        raise typer.Exit(code=1)
