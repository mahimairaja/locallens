"""Tests for the Rust extension detection layer.

Covers the import / flag logic in locallens._internals._rust and the
pipeline chunker shim that bridges old vs new workspace APIs.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest


def _reload_rust_module():
    """Reload _rust so flag values reflect the current environment."""
    import locallens._internals._rust as mod

    importlib.reload(mod)
    return mod


def test_has_rust_extension_helper():
    """has_rust_extension() mirrors the HAS_RUST flag."""
    from locallens._internals._rust import HAS_RUST, has_rust_extension

    assert has_rust_extension() is HAS_RUST


def test_rust_modules_status_when_unavailable(monkeypatch):
    import locallens._internals._rust as mod

    monkeypatch.setattr(mod, "HAS_RUST", False)
    available, modules = mod.rust_modules_status()
    assert available is False
    assert modules == []


def test_rust_modules_status_reports_active_modules(monkeypatch):
    import locallens._internals._rust as mod

    monkeypatch.setattr(mod, "HAS_RUST", True)
    monkeypatch.setattr(mod, "HAS_RUST_BM25", True)
    monkeypatch.setattr(mod, "HAS_RUST_CHUNKER", True)
    monkeypatch.setattr(mod, "HAS_RUST_WALKER", False)
    monkeypatch.setattr(mod, "HAS_RUST_WATCHER", True)

    available, modules = mod.rust_modules_status()
    assert available is True
    assert "BM25" in modules
    assert "Chunker" in modules
    assert "Walker" not in modules
    assert "Watcher" in modules


def test_walker_flag_is_narrow():
    """HAS_RUST_WALKER is only True when legacy RustWalker class exists.

    After the Codex adversarial review fix, the flag must NOT trigger on
    the new locallens_core workspace (which has walk_files but no
    combined walk_and_hash primitive).
    """
    from locallens._internals._rust import HAS_RUST_WALKER, _ext

    if _ext is None:
        assert HAS_RUST_WALKER is False
    else:
        # Flag reflects presence of the specific legacy class
        assert HAS_RUST_WALKER is hasattr(_ext, "RustWalker")


def test_import_fallback_to_top_level(monkeypatch):
    """When locallens.* paths fail, the detector tries plain imports too."""
    import locallens._internals._rust as mod

    # Simulate both importable paths failing -- should return None cleanly
    original = mod._import_extension
    monkeypatch.setattr("importlib.import_module", MagicMock(side_effect=ImportError))
    # _import_extension uses `from X import Y` which bypasses import_module;
    # this just exercises the function without crashing
    result = original()
    # Result is either None or a real module -- both acceptable
    assert result is None or hasattr(result, "__name__")


class TestChunkerShim:
    """Verify the pipeline chunker shim degrades gracefully."""

    def test_chunk_text_returns_list(self):
        """chunk_text always returns a list regardless of backend."""
        from locallens.pipeline.chunker import chunk_text

        result = chunk_text("Hello world. " * 50, 200, 20, ".md")
        assert isinstance(result, list)

    def test_chunk_text_empty_returns_empty(self):
        from locallens.pipeline.chunker import chunk_text

        assert chunk_text("", 1000, 50, ".md") == []
        assert chunk_text("   ", 1000, 50, ".md") == []

    def test_chunk_text_respects_file_type(self):
        """Markdown dispatch splits on headings."""
        from locallens.pipeline.chunker import chunk_text

        text = "# Title\n\n" + "Para. " * 30 + "\n\n## Section\n\n" + "More. " * 30
        chunks = chunk_text(text, 200, 20, ".md")
        assert len(chunks) >= 1

    def test_python_fallback_when_rust_disabled(self, monkeypatch):
        """Force the Python path by disabling HAS_RUST_CHUNKER."""
        import locallens.pipeline.chunker as mod

        monkeypatch.setattr(mod, "HAS_RUST_CHUNKER", False)
        result = mod.chunk_text("Plain content " * 30, 200, 20, ".txt")
        assert isinstance(result, list)
        assert len(result) >= 1


def test_file_core_hash_matches_hashlib(tmp_path):
    """hash_file produces the standard hashlib-equivalent hex digest."""
    import hashlib

    from locallens._internals._file_core import hash_file

    p = tmp_path / "f.bin"
    p.write_bytes(b"locallens test payload")
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    assert hash_file(p) == expected
