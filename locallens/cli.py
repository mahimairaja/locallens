"""Typer CLI for LocalLens: index, search, ask, voice, stats commands."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from locallens.config import DEFAULT_TOP_K, QDRANT_PATH, RAG_TOP_K

app = typer.Typer(
    name="locallens",
    help="Search your files by talking to them — 100% offline semantic search with voice.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def index(
    folder_path: Path = typer.Argument(..., help="Path to the folder to index."),
    force: bool = typer.Option(False, "--force", help="Re-index all files, ignoring hash cache."),
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
    top_k: int = typer.Option(DEFAULT_TOP_K, "--top-k", help="Number of results to return."),
) -> None:
    """Semantic search over your indexed files."""
    from locallens import store as st
    from locallens.searcher import search as do_search

    st.init()
    if st.count() == 0:
        console.print("[yellow]No files indexed yet. Run `locallens index <folder>` first.[/yellow]")
        raise typer.Exit()

    results = do_search(query, top_k)

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
    top_k: int = typer.Option(RAG_TOP_K, "--top-k", help="Number of chunks to retrieve for context."),
) -> None:
    """Ask a question about your indexed files using RAG."""
    from locallens import store as st
    from locallens.rag import ask as do_ask

    st.init()
    if st.count() == 0:
        console.print("[yellow]No files indexed yet. Run `locallens index <folder>` first.[/yellow]")
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
def voice() -> None:
    """Start the voice interface — speak to search your files."""
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
def stats() -> None:
    """Show statistics about the indexed collection."""
    from locallens import store as st

    st.init()
    total_chunks = st.count()
    total_files = st.get_file_count()

    table = Table(title="LocalLens Stats")
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("Total files indexed", str(total_files))
    table.add_row("Total chunks", str(total_chunks))
    table.add_row("Storage path", str(QDRANT_PATH))

    disk_usage = "N/A"
    if QDRANT_PATH.exists():
        total_bytes = sum(f.stat().st_size for f in QDRANT_PATH.rglob("*") if f.is_file())
        if total_bytes < 1024 * 1024:
            disk_usage = f"{total_bytes / 1024:.1f} KB"
        else:
            disk_usage = f"{total_bytes / (1024 * 1024):.1f} MB"

    table.add_row("Disk usage", disk_usage)
    console.print(table)
