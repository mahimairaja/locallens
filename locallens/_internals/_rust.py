"""Runtime capability flags for the optional Rust extension.

Tries three import paths in order:

1. ``locallens_core`` -- the separate ``locallens-core`` PyPI package
   (new workspace layout under ``rust/``).
2. ``locallens._locallens_rs`` -- the in-package maturin layout
   (legacy flat ``src/`` layout).
3. ``_locallens_rs`` -- top-level fallback for manual installs.

When none succeed, all ``HAS_RUST*`` flags stay False and callers
fall back to the pure-Python implementation.
"""

from __future__ import annotations

import logging
from types import ModuleType
from typing import cast

log = logging.getLogger(__name__)

HAS_RUST: bool = False
HAS_RUST_BM25: bool = False
HAS_RUST_CHUNKER: bool = False
HAS_RUST_WALKER: bool = False
HAS_RUST_WATCHER: bool = False


def _import_extension() -> ModuleType | None:
    """Try import paths in preference order."""
    # 1. New workspace layout: separate locallens-core package
    try:
        import locallens_core  # type: ignore[import-not-found]

        return cast(ModuleType, locallens_core)
    except ImportError:
        pass
    # 2. In-package maturin layout (legacy)
    try:
        from locallens import _locallens_rs  # type: ignore[attr-defined]

        return cast(ModuleType, _locallens_rs)
    except ImportError:
        pass
    # 3. Top-level fallback
    try:
        import _locallens_rs  # type: ignore[import-not-found]

        return cast(ModuleType, _locallens_rs)
    except ImportError as exc:
        log.debug("Rust extension not available (pure-Python fallback): %s", exc)
        return None


_ext = _import_extension()
if _ext is not None:
    HAS_RUST = True
    # New workspace layout uses different flag names
    HAS_RUST_BM25 = bool(getattr(_ext, "HAS_BM25", False)) or hasattr(_ext, "BM25Index")
    HAS_RUST_CHUNKER = bool(getattr(_ext, "HAS_CHUNKER", False)) or hasattr(
        _ext, "chunk_text"
    )
    HAS_RUST_WALKER = bool(getattr(_ext, "HAS_WALKER", False)) or hasattr(
        _ext, "walk_files"
    )
    HAS_RUST_WATCHER = bool(getattr(_ext, "HAS_WATCHER", False)) or hasattr(
        _ext, "FileWatcher"
    )


def has_rust_extension() -> bool:
    """Return True when the compiled Rust extension is importable."""
    return HAS_RUST


def rust_modules_status() -> tuple[bool, list[str]]:
    """Return ``(is_available, active_module_names)`` for doctor output."""
    if not HAS_RUST:
        return False, []
    modules = [
        name
        for name, flag in [
            ("BM25", HAS_RUST_BM25),
            ("Chunker", HAS_RUST_CHUNKER),
            ("Walker", HAS_RUST_WALKER),
            ("Watcher", HAS_RUST_WATCHER),
        ]
        if flag
    ]
    return True, modules
