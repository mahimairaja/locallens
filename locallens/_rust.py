"""Runtime capability flags for the optional Rust extension.

Today the extension does not exist; ``HAS_RUST`` is always ``False`` and
every caller falls back to the pure-Python implementation. When a later PR
lands the PyO3 crate, it exports ``HAS_BM25`` / ``HAS_CHUNKER`` / ``HAS_WALKER``
symbols on the extension module and the matching flags below flip to
``True`` on import.

This module is imported eagerly at module-load time by any caller that
wants to branch on Rust availability. The import must never raise — a
failed import of ``_locallens_rs`` is the expected state until the crate
is built.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

HAS_RUST: bool = False
HAS_RUST_BM25: bool = False
HAS_RUST_CHUNKER: bool = False
HAS_RUST_WALKER: bool = False

try:
    import _locallens_rs  # type: ignore[import-not-found]

    HAS_RUST = True
    HAS_RUST_BM25 = bool(getattr(_locallens_rs, "HAS_BM25", False))
    HAS_RUST_CHUNKER = bool(getattr(_locallens_rs, "HAS_CHUNKER", False))
    HAS_RUST_WALKER = bool(getattr(_locallens_rs, "HAS_WALKER", False))
except ImportError as exc:
    # DEBUG, not WARNING: the extension is optional and missing-by-default
    # until a later PR ships the compiled wheel. A WARNING would spam every
    # import with something the user can't act on.
    log.debug("Rust extension not available (pure-Python fallback): %s", exc)


def has_rust_extension() -> bool:
    """Return True when the compiled Rust extension is importable.

    Callers that want finer-grained capability detection should read the
    module-level ``HAS_RUST_BM25`` / ``HAS_RUST_CHUNKER`` / ``HAS_RUST_WALKER``
    constants directly — a single extension may ship subsets of the modules
    during the rollout.
    """
    return HAS_RUST
