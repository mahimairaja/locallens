"""Runtime capability flags for the optional Rust extension.

The compiled extension at ``locallens._locallens_rs`` (built by maturin;
see ``pyproject.toml`` ``[tool.maturin]``) exports module-level
``HAS_BM25`` / ``HAS_CHUNKER`` / ``HAS_WALKER`` booleans so the rollout
can ship one module at a time. This file reads those flags on import and
re-exports:

- ``HAS_RUST`` — True iff the extension imports at all.
- ``HAS_RUST_BM25`` — True iff the extension advertises the BM25 class.
- ``HAS_RUST_CHUNKER``, ``HAS_RUST_WALKER`` — reserved for future modules
  (always False today).

Install layout: maturin with ``module-name = "locallens._locallens_rs"``
installs the compiled extension inside the package, reachable as
``locallens._locallens_rs``. We try that path first, then fall back to a
top-level ``_locallens_rs`` import so a manually-installed or legacy-layout
extension still works.

This module is imported eagerly at module-load time by any caller that
wants to branch on Rust availability. The import must never raise — when
a user installs from sdist without a Rust toolchain (or uses an
unsupported platform), the ``HAS_RUST*`` flags stay False and callers
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
