"""BM25 keyword index for hybrid search (backend side).

Thin wrapper around ``locallens._bm25_core._Bm25Index``. The module-level
API is preserved for callers: ``build_index``, ``add_documents``,
``remove_documents``, ``search``, ``load``, ``is_loaded``, plus ``flush``.

Persists to ``data/bm25_index.json`` (relative to the process CWD) by default.
"""

from __future__ import annotations

import logging
from pathlib import Path

from locallens._bm25_core import _Bm25Index

logger = logging.getLogger(__name__)

_BM25_PATH = Path("data/bm25_index.json")

_index = _Bm25Index(_BM25_PATH, logger=logger)

build_index = _index.build_index
add_documents = _index.add_documents
remove_documents = _index.remove_documents
search = _index.search
load = _index.load
is_loaded = _index.is_loaded
flush = _index.flush


def _set_persist_path(path: Path) -> None:
    """Redirect the underlying index to a new on-disk path.

    Kept symmetrical with the CLI-side wrapper for tests that exercise both.
    """
    _index.set_persist_path(path)
