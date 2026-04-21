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
    from locallens.integrations import sync

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

    from locallens.integrations import sync
    from locallens.pipeline import store as st

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
    format: str = typer.Option("rich", "--format", help="Output format: rich or json"),
) -> None:
    """Index local files into the vector database for semantic search."""
    if not folder_path.is_dir():
        if format == "json":
            import json

            print(json.dumps({"error": f"'{folder_path}' is not a valid directory."}))
            raise typer.Exit(code=1)
        console.print(f"[red]Error: '{folder_path}' is not a valid directory.[/red]")
        raise typer.Exit(code=1)

    from locallens import LocalLens

    lens = LocalLens(path=str(folder_path))
    result = lens.index(force=force)

    if format == "json":
        import json

        print(json.dumps(result.to_dict(), indent=2))
    else:
        console.print(
            f"\n[green]Indexed {result.total_files} files "
            f"({result.total_chunks} chunks) in {result.duration_seconds:.1f}s.[/green]"
        )


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
    format: str = typer.Option("rich", "--format", help="Output format: rich or json"),
) -> None:
    """Semantic search over your indexed files.

    Supports query arithmetic: use + to add concepts and - to subtract.
    Example: locallens search "pricing +recent -draft"
    """
    from locallens import LocalLens
    from locallens.pipeline.query_parser import parse_query

    parsed = parse_query(query)
    lens = LocalLens()
    results = lens.search(
        query, top_k=top_k, file_type=file_type, path_prefix=path_prefix
    )

    if format == "json":
        import json

        output = [r.to_dict() for r in results]
        if parsed.is_arithmetic:
            print(
                json.dumps(
                    {"parsed_terms": parsed.to_dict(), "results": output}, indent=2
                )
            )
        else:
            print(json.dumps(output, indent=2))
        return

    # Show parsed query components when arithmetic is used
    if parsed.is_arithmetic:
        parts = []
        for t in parsed.terms:
            if t.sign > 0:
                parts.append(f"[green]+[/green] {t.text}")
            else:
                parts.append(f"[red]-[/red] {t.text}")
        console.print(f"Query arithmetic: {' '.join(parts)}")

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
        preview = hit.chunk_text[:200]
        if len(hit.chunk_text) > 200:
            preview += "..."
        table.add_row(
            str(rank),
            f"{hit.score:.2f}",
            hit.file_name,
            hit.file_path,
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
    format: str = typer.Option("rich", "--format", help="Output format: rich or json"),
) -> None:
    """Ask a question about your indexed files using RAG."""
    from locallens import LocalLens
    from locallens.models import OllamaUnavailableError

    lens = LocalLens()

    if format == "json":
        import json

        try:
            result = lens.ask(question, top_k=top_k)
            print(json.dumps(result.to_dict(), indent=2))
        except OllamaUnavailableError as exc:
            print(json.dumps({"error": str(exc)}))
            raise typer.Exit(code=1)
        return

    # Rich streaming mode
    try:
        for event in lens.ask_stream(question, top_k=top_k):
            if event.event_type == "token":
                console.print(event.data, end="")
        console.print()
    except OllamaUnavailableError:
        console.print(
            Panel(
                "[red]Ollama is not running.[/red]\n\n"
                "Start it with: [bold]ollama serve[/bold]\n"
                "Pull the model: [bold]ollama pull qwen2.5:3b[/bold]",
                title="Ollama Unavailable",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"\n[red]Error: {exc}[/red]")
        raise typer.Exit(code=1)


@app.command()
def voice(
    namespace: str = typer.Option("default", "--namespace", help="Namespace to use."),
) -> None:
    """Start the voice interface -- speak to search your files."""
    try:
        from locallens.integrations.voice import start_voice_loop
    except ImportError:
        console.print(
            "[red]Voice dependencies not installed.[/red]\n"
            "Install them with: [bold]pip install locallens\\[voice][/bold]"
        )
        raise typer.Exit(code=1)

    from locallens.pipeline import store as st
    from locallens.pipeline.embedder import embed_query

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

    from locallens.config import SUPPORTED_EXTENSIONS
    from locallens.pipeline import store as st

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
                from locallens.pipeline.indexer import index_folder

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
    format: str = typer.Option("rich", "--format", help="Output format: rich or json"),
) -> None:
    """Show statistics about the indexed collection."""
    from locallens import LocalLens

    lens = LocalLens()

    if format == "json":
        import json

        result = lens.stats()
        print(json.dumps(result.to_dict(), indent=2))
        return

    from locallens.pipeline import store as st

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
def doctor(
    format: str = typer.Option("rich", "--format", help="Output format: rich or json"),
) -> None:
    """Run health checks on all LocalLens dependencies."""
    if format == "json":
        import json

        from locallens import LocalLens

        lens = LocalLens()
        checks = lens.doctor()
        critical_ok = all(
            c.status != "fail"
            for c in checks
            if c.name in ("Qdrant Edge", "Embedding Model")
        )
        print(
            json.dumps(
                {
                    "checks": [c.to_dict() for c in checks],
                    "exit_code": 0 if critical_ok else 1,
                },
                indent=2,
            )
        )
        raise typer.Exit(code=0 if critical_ok else 1)
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
        from locallens.pipeline import store as st

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

    # 8. Rust extensions
    from locallens._internals._rust import rust_modules_status

    available, modules = rust_modules_status()
    if available:
        table.add_row("Rust Extensions", PASS, f"Active: {', '.join(modules)}")
    else:
        table.add_row(
            "Rust Extensions",
            "[yellow]-[/yellow]",
            "Not available (pure-Python fallback)",
        )

    # 9. Schema version
    try:
        from locallens.pipeline.schema import get_schema

        schema = get_schema(COLLECTION_NAME)
        if schema:
            table.add_row(
                "Schema Version",
                PASS,
                f"v{schema.current.version} ({len(schema.current.payload_fields)} fields)",
            )
        else:
            table.add_row(
                "Schema Version",
                "[yellow]-[/yellow]",
                "Not initialized (run index first)",
            )
    except Exception:
        table.add_row("Schema Version", "[yellow]-[/yellow]", "Could not check")

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


# ── serve command group ──────────────────────────────────────────

serve_app = typer.Typer(
    name="serve",
    help="Start LocalLens servers: MCP for AI agents, API for REST, or UI for the dashboard.",
    no_args_is_help=True,
)
app.add_typer(serve_app)


@serve_app.callback(invoke_without_command=True)
def serve_default(
    ctx: typer.Context,
    mcp: bool = typer.Option(False, "--mcp", help="Start MCP server for AI agents"),
    api: bool = typer.Option(False, "--api", help="Start headless REST API server"),
    ui: bool = typer.Option(
        False, "--ui", help="Start full web dashboard with React UI"
    ),
    port: int = typer.Option(None, "--port", help="Custom port"),
) -> None:
    """Start a LocalLens server."""
    if mcp:
        try:
            from locallens.serve.mcp_server import main as mcp_main
        except ImportError:
            console.print(
                "[red]MCP dependencies not installed.[/red]\n"
                "Install with: [bold]pip install locallens\\[mcp][/bold]"
            )
            raise typer.Exit(code=1)
        mcp_main(port=port or 8811)
    elif api:
        try:
            from locallens.serve.dashboard import start_api
        except ImportError:
            console.print(
                "[red]Server dependencies not installed.[/red]\n"
                "Install with: [bold]pip install locallens\\[server][/bold]"
            )
            raise typer.Exit(code=1)
        start_api(port=port or 8000)
    elif ui:
        try:
            from locallens.serve.dashboard import start_dashboard
        except ImportError:
            console.print(
                "[red]Server dependencies not installed.[/red]\n"
                "Install with: [bold]pip install locallens\\[server][/bold]"
            )
            raise typer.Exit(code=1)
        start_dashboard(port=port or 8000, with_ui=True)
    elif ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


# ── schema command group ────────────────────────────────────────────

schema_app = typer.Typer(
    name="schema",
    help="Inspect and manage the collection schema.",
    no_args_is_help=True,
)
app.add_typer(schema_app)


@schema_app.command("show")
def schema_show(
    collection: str = typer.Option(
        "locallens", "--collection", help="Collection name."
    ),
) -> None:
    """Print the current schema for a collection."""
    from locallens.pipeline.schema import get_schema

    schema = get_schema(collection)
    if schema is None:
        console.print(f"[yellow]No schema stored for '{collection}'.[/yellow]")
        console.print("Run [bold]locallens index <folder>[/bold] to initialize.")
        raise typer.Exit()

    table = Table(title=f"Schema: {collection} (v{schema.current.version})")
    table.add_column("Field", style="bold")
    table.add_column("Type")
    for field_name, field_type in schema.current.payload_fields.items():
        table.add_row(field_name, field_type)
    console.print(table)

    console.print(f"\nVector: [cyan]{schema.current.vector_config}[/cyan]")
    console.print(f"Created: {schema.current.created_at}")


@schema_app.command("history")
def schema_history(
    collection: str = typer.Option(
        "locallens", "--collection", help="Collection name."
    ),
) -> None:
    """Print all schema versions for a collection."""
    from locallens.pipeline.schema import get_schema

    schema = get_schema(collection)
    if schema is None:
        console.print(f"[yellow]No schema history for '{collection}'.[/yellow]")
        raise typer.Exit()

    table = Table(title=f"Schema History: {collection}")
    table.add_column("Version", style="bold", width=8)
    table.add_column("Fields", width=12)
    table.add_column("Created")
    for v in schema.history:
        table.add_row(str(v.version), str(len(v.payload_fields)), v.created_at)
    console.print(table)
