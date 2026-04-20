"""Runtime capability flags for the optional Rust extension.

Today the extension does not exist; ``HAS_RUST`` is always ``False`` and
every caller falls back to the pure-Python implementation. When a later PR
lands the PyO3 crate, it exports ``HAS_BM25`` / ``HAS_CHUNKER`` / ``HAS_WALKER``
symbols on the extension module and the matching flags below flip to
``True`` on import.

Install layout: maturin with ``module-name = "locallens._locallens_rs"``
(per the CUTOVER block in ``pyproject.toml``) installs the compiled
extension inside the package, reachable as ``locallens._locallens_rs``.
We try that path first, then fall back to a top-level ``_locallens_rs``
import so a manually-installed or legacy-layout extension still works.

This module is imported eagerly at module-load time by any caller that
wants to branch on Rust availability. The import must never raise — a
failed import of the extension is the expected state until the crate
is built.
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


def _import_extension() -> ModuleType | None:
    """Try the in-package layout first, then the top-level fallback."""
    try:
        from locallens import _locallens_rs  # type: ignore[attr-defined]

        return cast(ModuleType, _locallens_rs)
    except ImportError:
        pass
    try:
        import _locallens_rs  # type: ignore[import-not-found]

        return cast(ModuleType, _locallens_rs)
    except ImportError as exc:
        log.debug("Rust extension not available (pure-Python fallback): %s", exc)
        return None


_ext = _import_extension()
if _ext is not None:
    HAS_RUST = True
    HAS_RUST_BM25 = bool(getattr(_ext, "HAS_BM25", False))
    HAS_RUST_CHUNKER = bool(getattr(_ext, "HAS_CHUNKER", False))
    HAS_RUST_WALKER = bool(getattr(_ext, "HAS_WALKER", False))


def has_rust_extension() -> bool:
    """Return True when the compiled Rust extension is importable.

    Callers that want finer-grained capability detection should read the
    module-level ``HAS_RUST_BM25`` / ``HAS_RUST_CHUNKER`` / ``HAS_RUST_WALKER``
    constants directly — a single extension may ship subsets of the modules
    during the rollout.
    """
    return HAS_RUST
