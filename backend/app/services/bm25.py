"""BM25 keyword index for hybrid search (backend side).

Thin wrapper. Prefers the compiled Rust ``RustBM25`` when available, falls
back to the pure-Python ``_Bm25Index`` otherwise. Both implementations share
the same public API and on-disk JSON format.

Persists to ``data/bm25_index.json`` (relative to the process CWD) by default.
"""

from __future__ import annotations

import logging
from pathlib import Path

from locallens._internals._rust import HAS_RUST_BM25

logger = logging.getLogger(__name__)

if HAS_RUST_BM25:
    try:
        from locallens_core import BM25Index as _RustBM25Cls  # type: ignore[import-not-found]
    except ImportError:
        from locallens._locallens_rs import RustBM25 as _RustBM25Cls  # type: ignore[attr-defined,no-redef]

    def _make_index(path: Path) -> object:
        return _RustBM25Cls(path)
else:
    from locallens._internals._bm25_core import _Bm25Index

    def _make_index(path: Path) -> object:
        return _Bm25Index(path, logger=logger)


_BM25_PATH = Path("data/bm25_index.json")

_index = _make_index(_BM25_PATH)

build_index = _index.build_index  # type: ignore[attr-defined]
add_documents = _index.add_documents  # type: ignore[attr-defined]
remove_documents = _index.remove_documents  # type: ignore[attr-defined]
search = _index.search  # type: ignore[attr-defined]
load = _index.load  # type: ignore[attr-defined]
is_loaded = _index.is_loaded  # type: ignore[attr-defined]
flush = _index.flush  # type: ignore[attr-defined]


def _set_persist_path(path: Path) -> None:
    """Redirect the underlying index to a new on-disk path.

    Kept symmetrical with the CLI-side wrapper for tests that exercise both.
    """
    _index.set_persist_path(path)  # type: ignore[attr-defined]
