"""Fallback wrapper: prefers Rust (locallens_core) when available,
falls back to pure Python implementations transparently.

Usage::

    from locallens.fast import BM25Index, chunk_text, walk_files, RUST_AVAILABLE
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

RUST_AVAILABLE: bool = False
_rust_ok = False

try:
    import locallens_core as _lc  # type: ignore[import-not-found]

    _rust_ok = True
except ImportError:
    _lc = None  # type: ignore[assignment]

# ── BM25 ────────────────────────────────────────────────────────────

if _rust_ok:
    BM25Index = _lc.BM25Index
    RUST_AVAILABLE = True
else:
    from locallens._internals._bm25_core import _Bm25Index as BM25Index  # type: ignore[assignment] # noqa: F401

# ── Chunker ─────────────────────────────────────────────────────────

if _rust_ok:
    chunk_text = _lc.chunk_text
    chunk_structured = _lc.chunk_structured
    chunk_batch = _lc.chunk_batch
    supported_languages = _lc.supported_languages
    RUST_AVAILABLE = True
else:
    from locallens.pipeline.chunker import chunk_text  # type: ignore[assignment] # noqa: F401

    def chunk_structured(  # type: ignore[misc]
        text: str,
        file_type: str,
        max_size: int = 1000,
        overlap: int = 50,
        min_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fallback: delegates to chunk_text with file_type dispatch."""
        from locallens.pipeline.chunker import chunk_text as _chunk

        chunks = _chunk(text, max_size, overlap, file_type)
        offset = 0
        results = []
        for c in chunks:
            idx = text.find(c, offset)
            start = idx if idx >= 0 else offset
            results.append(
                {"text": c, "start_offset": start, "end_offset": start + len(c)}
            )
            offset = start + len(c)
        return results

    def chunk_batch(  # type: ignore[misc]
        documents: list[tuple[str, str]],
        max_size: int = 1000,
        overlap: int = 50,
        min_size: int = 100,
    ) -> list[list[dict[str, Any]]]:
        return [
            chunk_structured(text, ft, max_size, overlap, min_size)
            for text, ft in documents
        ]

    def supported_languages() -> list[dict[str, Any]]:  # type: ignore[misc]
        return [
            {"name": "markdown", "aliases": ["md"], "extensions": [".md", ".mdx"]},
            {"name": "python", "aliases": ["py"], "extensions": [".py"]},
        ]


# ── Walker ──────────────────────────────────────────────────────────

if _rust_ok:
    walk_files = _lc.walk_files
    extract_texts = _lc.extract_texts
    RUST_AVAILABLE = True
else:
    walk_files = None  # type: ignore[assignment]
    extract_texts = None  # type: ignore[assignment]

# ── Watcher ─────────────────────────────────────────────────────────

if _rust_ok:
    FileWatcher = _lc.FileWatcher
    RUST_AVAILABLE = True
else:
    try:
        from locallens._internals._watcher import FileWatcher  # type: ignore[assignment] # noqa: F401
    except ImportError:
        FileWatcher = None  # type: ignore[assignment,misc]


def get_backend() -> str:
    """Return ``"rust"`` if locallens_core is importable, else ``"python"``."""
    return "rust" if RUST_AVAILABLE else "python"
