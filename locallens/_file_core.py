"""Shared file-discovery + SHA-256 core.

Replaces the walker + hasher that was duplicated across
``locallens/indexer.py``, ``backend/app/services/indexer.py``, and
``backend/app/services/watcher.py``. All three now call
:func:`walk_and_hash` (or :func:`hash_file` for single-file paths).

When the Rust extension is available (see ``locallens._rust.HAS_RUST_WALKER``)
the heavy work runs in the ``_locallens_rs.RustWalker`` class, which uses
``walkdir`` for traversal and ``rayon`` for parallel SHA-256 across cores.
The pure-Python fallback (:class:`_PyWalker`) replicates the old
``Path.rglob`` + streaming ``hashlib.sha256`` behaviour verbatim, so both
paths produce byte-identical results.

Hash output is lowercase hex, 64 chars — matches ``hashlib.sha256(b).hexdigest()``
so Qdrant payload-index ``has_hash`` comparisons keep working across an
upgrade or downgrade.

Env knobs:
- ``LOCALLENS_WALK_PARALLEL=0`` disables rayon parallelism (useful on HDDs
  where parallel reads can be slower than sequential).
- ``RAYON_NUM_THREADS=N`` (rayon-native) caps the thread pool size.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import NamedTuple

from locallens._rust import HAS_RUST_WALKER


class FileEntry(NamedTuple):
    path: Path
    sha256: str
    size: int


def _parallel_enabled(parallel: bool) -> bool:
    """Respect LOCALLENS_WALK_PARALLEL=0 as a runtime override."""
    if not parallel:
        return False
    override = os.environ.get("LOCALLENS_WALK_PARALLEL", "").strip().lower()
    if override in {"0", "false", "no", "off"}:
        return False
    return True


def hash_file(path: Path) -> str:
    """Streaming SHA-256 of a single file, hex-encoded.

    Output is byte-identical to ``hashlib.sha256(path.read_bytes()).hexdigest()``
    regardless of which backend runs it.
    """
    if HAS_RUST_WALKER:
        from locallens._locallens_rs import RustWalker  # type: ignore[attr-defined]

        result: str = RustWalker.hash_file(str(path))
        return result
    return _py_hash_file(path)


def walk_and_hash(
    root: Path,
    extensions: frozenset[str],
    *,
    max_file_size_bytes: int,
    skip_hidden: bool = True,
    follow_symlinks: bool = True,
    parallel: bool = True,
) -> list[FileEntry]:
    """Walk ``root``, filter, hash each kept file.

    Returns entries sorted by path for deterministic output across
    implementations and Python versions.

    ``extensions`` must be lowercase and include the leading dot, e.g.
    ``frozenset({".py", ".md"})``. Matching is case-insensitive so
    ``FOO.PY`` is kept when ``.py`` is in the set.

    Files that cannot be opened (permission denied, I/O error) are
    silently skipped — matches the pre-existing warn-and-continue
    behaviour of the CLI indexer. Callers that need to surface those
    errors should walk explicitly with ``Path.rglob`` and call
    :func:`hash_file` per file.
    """
    if not root.exists():
        return []

    run_parallel = _parallel_enabled(parallel)
    ext_list = [e.lower() for e in extensions]

    if HAS_RUST_WALKER:
        from locallens._locallens_rs import RustWalker  # type: ignore[attr-defined]

        walker = RustWalker(
            ext_list,
            max_file_size_bytes,
            skip_hidden=skip_hidden,
            follow_symlinks=follow_symlinks,
            parallel=run_parallel,
        )
        raw = walker.walk_and_hash(str(root))
        return [FileEntry(Path(p), sha, size) for p, sha, size in raw]

    return _PyWalker(
        extensions=frozenset(ext_list),
        max_file_size_bytes=max_file_size_bytes,
        skip_hidden=skip_hidden,
        follow_symlinks=follow_symlinks,
    ).walk_and_hash(root)


# ---------------------------------------------------------------------------
# Pure-Python fallback — mirrors the pre-refactor indexer.py implementation.
# ---------------------------------------------------------------------------


def _py_hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _is_hidden_relative(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


class _PyWalker:
    """Pure-Python reference implementation — used when Rust isn't built."""

    def __init__(
        self,
        *,
        extensions: frozenset[str],
        max_file_size_bytes: int,
        skip_hidden: bool,
        follow_symlinks: bool,
    ) -> None:
        self._extensions = frozenset(e.lower() for e in extensions)
        self._max_size = max_file_size_bytes
        self._skip_hidden = skip_hidden
        self._follow_symlinks = follow_symlinks

    def walk_and_hash(self, root: Path) -> list[FileEntry]:
        entries: list[FileEntry] = []
        for raw in sorted(root.rglob("*")):
            # rglob follows symlinked directories but doesn't resolve;
            # is_file() returns True for a symlink pointing at a file
            # when follow_symlinks is True (the default for Path.is_file).
            if not raw.is_file():
                continue
            if self._skip_hidden and _is_hidden_relative(raw, root):
                continue
            if raw.suffix.lower() not in self._extensions:
                continue
            try:
                size = raw.stat().st_size
            except OSError:
                continue
            if size > self._max_size:
                continue
            try:
                sha = _py_hash_file(raw)
            except OSError:
                continue
            entries.append(FileEntry(raw, sha, size))
        return entries
