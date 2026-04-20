"""BM25 keyword index for hybrid search (CLI side).

Thin wrapper around ``locallens._bm25_core._Bm25Index``. The module-level
API is preserved for callers: ``build_index``, ``add_documents``,
``remove_documents``, ``search``, ``load``, ``is_loaded``, plus ``flush``.

Persists to ``~/.locallens/bm25_index.json`` by default.
"""

from __future__ import annotations

from pathlib import Path

from locallens._bm25_core import _Bm25Index

_BM25_PATH = Path.home() / ".locallens" / "bm25_index.json"

_index = _Bm25Index(_BM25_PATH)

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
