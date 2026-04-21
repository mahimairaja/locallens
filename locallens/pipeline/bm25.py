"""BM25 keyword index for hybrid search (CLI side).

Thin wrapper. When the compiled Rust extension is available (see
``locallens._rust``), this module uses ``RustBM25`` for the in-memory index;
otherwise it falls back to the pure-Python ``_Bm25Index``. Both implementations
expose the same public API — ``build_index``, ``add_documents``,
``remove_documents``, ``search``, ``load``, ``is_loaded``, ``flush``,
``set_persist_path`` — and read/write the same on-disk JSON shape, so
switching between them never requires migration.

Persists to ``~/.locallens/bm25_index.json`` by default.
"""

from __future__ import annotations

from pathlib import Path

from locallens._internals._rust import HAS_RUST_BM25

if HAS_RUST_BM25:
    try:
        from locallens_core import BM25Index as _IndexImpl  # type: ignore[import-not-found,assignment]
    except ImportError:
        from locallens._locallens_rs import (  # type: ignore[attr-defined,no-redef]
            RustBM25 as _IndexImpl,
        )
else:
    from locallens._internals._bm25_core import (
        _Bm25Index as _IndexImpl,  # type: ignore[assignment]
    )

_BM25_PATH = Path.home() / ".locallens" / "bm25_index.json"

_index = _IndexImpl(_BM25_PATH)

# Module-level re-exports so existing callers (``bm25.add_documents(...)``)
# keep working without change.
build_index = _index.build_index
add_documents = _index.add_documents
remove_documents = _index.remove_documents
search = _index.search
load = _index.load
is_loaded = _index.is_loaded
flush = _index.flush


def _set_persist_path(path: Path) -> None:
    """Redirect the underlying index to a new on-disk path.

    Used by tests and ``scripts/bench_pipeline.py`` to point the singleton at
    an isolated directory so benchmarks don't touch the user's real index.
    """
    _index.set_persist_path(path)
