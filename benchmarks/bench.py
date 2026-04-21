#!/usr/bin/env python3
"""Benchmark: Python vs Rust performance comparison.

Prints a Rich table showing timings for BM25, chunking, and file walking
with both backends. Requires the Rust extension (locallens-core) to be
installed for the Rust column.

Usage:
    python benchmarks/bench.py
    make bench
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def _generate_corpus(n_docs: int) -> list[tuple[str, str]]:
    """Generate synthetic (doc_id, text) pairs."""
    import random

    rng = random.Random(42)
    words = "the quick brown fox jumps over lazy dog alpha beta gamma delta".split()
    docs = []
    for i in range(n_docs):
        length = rng.randint(50, 300)
        text = " ".join(rng.choice(words) for _ in range(length))
        docs.append((f"doc_{i}", text))
    return docs


def _generate_files(folder: Path, n_files: int) -> None:
    """Create synthetic text files."""
    import random

    rng = random.Random(42)
    words = "the quick brown fox jumps over lazy dog".split()
    for i in range(n_files):
        ext = rng.choice([".txt", ".md", ".py"])
        text = " ".join(rng.choice(words) for _ in range(rng.randint(100, 500)))
        (folder / f"file_{i}{ext}").write_text(text)


def bench_bm25(corpus: list[tuple[str, str]], queries: list[str]) -> dict[str, float]:
    """Benchmark BM25 build and query."""
    results: dict[str, float] = {}

    # Python BM25
    from locallens._internals._bm25_core import _Bm25Index

    idx = _Bm25Index(Path(tempfile.mktemp(suffix=".json")))
    t0 = time.perf_counter()
    for doc_id, text in corpus:
        idx.add_internal(doc_id, text)
    results["python_build_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    for q in queries:
        idx.search(q)
    results["python_query_ms"] = (time.perf_counter() - t0) * 1000

    # Rust BM25
    try:
        from locallens_core import BM25Index  # type: ignore[import-not-found]

        ridx = BM25Index(tempfile.mktemp(suffix=".json"))
        t0 = time.perf_counter()
        ridx.build(corpus)
        results["rust_build_ms"] = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        for q in queries:
            ridx.search(q)
        results["rust_query_ms"] = (time.perf_counter() - t0) * 1000
    except ImportError:
        results["rust_build_ms"] = -1
        results["rust_query_ms"] = -1

    return results


def bench_chunking(corpus: list[tuple[str, str]]) -> dict[str, float]:
    """Benchmark chunking."""
    results: dict[str, float] = {}
    texts = [(text, ".md") for _, text in corpus[:1000]]

    # Python chunker
    from locallens.pipeline.chunker import _chunk_markdown

    t0 = time.perf_counter()
    for text, _ in texts:
        _chunk_markdown(text, 500, 50)
    results["python_ms"] = (time.perf_counter() - t0) * 1000

    # Rust chunker
    try:
        from locallens_core import chunk_batch  # type: ignore[import-not-found]

        items = [(t, ft, 500, 50, 100) for t, ft in texts]  # noqa: F841
        t0 = time.perf_counter()
        chunk_batch([(t, ft) for t, ft in texts], 500, 50, 100)
        results["rust_ms"] = (time.perf_counter() - t0) * 1000
    except ImportError:
        results["rust_ms"] = -1

    return results


def bench_walking(n_files: int) -> dict[str, float]:
    """Benchmark file walking."""
    results: dict[str, float] = {}

    with tempfile.TemporaryDirectory() as d:
        _generate_files(Path(d), n_files)

        # Python walk
        t0 = time.perf_counter()
        list(Path(d).rglob("*"))
        results["python_ms"] = (time.perf_counter() - t0) * 1000

        # Rust walk
        try:
            from locallens_core import walk_files  # type: ignore[import-not-found]

            t0 = time.perf_counter()
            walk_files(d)
            results["rust_ms"] = (time.perf_counter() - t0) * 1000
        except ImportError:
            results["rust_ms"] = -1

    return results


def main() -> None:
    n_docs = 10000
    n_queries = 100
    n_files = 10000

    console.print(
        f"\n[bold]LocalLens Benchmark[/bold] ({n_docs} docs, {n_files} files)\n"
    )

    corpus = _generate_corpus(n_docs)
    queries = ["quick brown fox", "alpha beta", "lazy dog", "gamma delta", "jumps over"]
    queries = queries * (n_queries // len(queries))

    # BM25
    console.print("[cyan]Running BM25 benchmark...[/cyan]")
    bm25 = bench_bm25(corpus, queries)

    # Chunking
    console.print("[cyan]Running chunking benchmark...[/cyan]")
    chunking = bench_chunking(corpus)

    # Walking
    console.print("[cyan]Running file walking benchmark...[/cyan]")
    walking = bench_walking(n_files)

    # Results table
    table = Table(title="Performance Comparison")
    table.add_column("Benchmark", style="bold")
    table.add_column("Python", justify="right")
    table.add_column("Rust", justify="right")
    table.add_column("Speedup", justify="right", style="green")

    def _row(name: str, py_ms: float, rs_ms: float) -> None:
        if rs_ms < 0:
            table.add_row(name, f"{py_ms:.1f} ms", "N/A", "-")
        else:
            speedup = py_ms / rs_ms if rs_ms > 0 else 0
            table.add_row(name, f"{py_ms:.1f} ms", f"{rs_ms:.1f} ms", f"{speedup:.1f}x")

    _row(f"BM25 build ({n_docs} docs)", bm25["python_build_ms"], bm25["rust_build_ms"])
    _row(
        f"BM25 query ({n_queries} queries)",
        bm25["python_query_ms"],
        bm25["rust_query_ms"],
    )
    _row("Chunking (1000 docs)", chunking["python_ms"], chunking["rust_ms"])
    _row(f"File walking ({n_files} files)", walking["python_ms"], walking["rust_ms"])

    console.print()
    console.print(table)

    # Backend info
    try:
        from locallens.fast import RUST_AVAILABLE, get_backend

        console.print(
            f"\n[dim]Backend: {get_backend()} (RUST_AVAILABLE={RUST_AVAILABLE})[/dim]"
        )
    except ImportError:
        console.print("\n[dim]Backend: python (locallens.fast not available)[/dim]")


if __name__ == "__main__":
    main()
