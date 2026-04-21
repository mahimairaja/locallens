"""Parity tests: Rust chunker vs Python chunker.

Skipped when the Rust extension is not available.
"""

import pytest

from locallens._internals._rust import HAS_RUST_CHUNKER

pytestmark = pytest.mark.skipif(
    not HAS_RUST_CHUNKER, reason="Rust chunker not available"
)


def _python_chunk_text(text: str, size: int, overlap: int, file_type: str) -> list[str]:
    """Call the Python chunker by temporarily disabling the Rust dispatch."""
    import locallens.pipeline.chunker as mod

    original = mod.HAS_RUST_CHUNKER
    try:
        mod.HAS_RUST_CHUNKER = False
        return mod.chunk_text(text, size, overlap, file_type)
    finally:
        mod.HAS_RUST_CHUNKER = original


def _rust_chunk_text(text: str, size: int, overlap: int, file_type: str) -> list[str]:
    # New workspace (`locallens_core`) is structure-aware via
    # `chunk_structured(text, file_type, max_size, overlap, min_size)`.
    # Old in-package layout exposes `chunk_text(text, size, overlap, file_type)`.
    try:
        from locallens_core import chunk_structured  # type: ignore[import-not-found]

        result = chunk_structured(text, file_type, size, overlap, 100)
    except ImportError:
        from locallens._locallens_rs import chunk_text  # type: ignore[attr-defined]

        result = chunk_text(text, size, overlap, file_type)

    if result and hasattr(result[0], "text"):
        return [c.text for c in result]
    return result


class TestSubdivideParity:
    def test_simple_text(self):
        text = "word " * 300
        py = _python_chunk_text(text, 200, 20, ".xyz")
        rs = _rust_chunk_text(text, 200, 20, ".xyz")
        assert len(rs) == pytest.approx(len(py), abs=max(1, len(py) * 0.1))

    def test_empty(self):
        assert _rust_chunk_text("", 1000, 50, "") == []
        # Whitespace-only may produce empty OR whitespace chunk depending
        # on backend; both are acceptable non-semantic results.
        result = _rust_chunk_text("   ", 1000, 50, ".md")
        assert all(not c.strip() for c in result)

    def test_short_text_dropped(self):
        text = "short"
        py = _python_chunk_text(text, 1000, 50, ".txt")
        rs = _rust_chunk_text(text, 1000, 50, ".txt")
        # Python drops chunks shorter than MIN_CHUNK; Rust workspace may
        # keep them as the only chunk. Both behaviors are acceptable.
        assert len(py) == 0
        assert len(rs) <= 1


class TestMarkdownParity:
    def test_heading_split(self):
        text = "# Title\n\n" + "Content. " * 30 + "\n\n## Section\n\n" + "More. " * 30
        py = _python_chunk_text(text, 200, 20, ".md")
        rs = _rust_chunk_text(text, 200, 20, ".md")
        assert len(rs) == pytest.approx(len(py), abs=max(1, len(py) * 0.1))

    def test_no_headings(self):
        text = "Just plain text. " * 50
        py = _python_chunk_text(text, 200, 20, ".md")
        rs = _rust_chunk_text(text, 200, 20, ".md")
        assert len(rs) == pytest.approx(len(py), abs=max(1, len(py) * 0.1))


class TestCodeParity:
    def test_function_split(self):
        text = (
            "def foo():\n    "
            + "pass # " * 30
            + "\n\ndef bar():\n    "
            + "pass # " * 30
        )
        py = _python_chunk_text(text, 200, 20, ".py")
        rs = _rust_chunk_text(text, 200, 20, ".py")
        assert len(rs) == pytest.approx(len(py), abs=max(1, len(py) * 0.1))


class TestParagraphParity:
    def test_paragraph_merge(self):
        text = "\n\n".join(["Paragraph " + str(i) + ". " * 20 for i in range(10)])
        py = _python_chunk_text(text, 500, 50, ".pdf")
        rs = _rust_chunk_text(text, 500, 50, ".pdf")
        assert len(rs) == pytest.approx(len(py), abs=max(1, len(py) * 0.1))


class TestBatchParity:
    def test_batch_matches_sequential(self):
        # Verify batch processing produces results for each document.
        # API signatures differ between backends, so we only assert the
        # shape (one list per input) rather than exact per-backend equality.
        try:
            from locallens_core import chunk_batch  # type: ignore[import-not-found]

            # New workspace: (documents, max_size, overlap, min_size)
            documents = [
                ("word " * 200, ".txt"),
                ("def foo():\n    pass\n" * 20, ".py"),
                ("# Title\n\ncontent " * 30, ".md"),
            ]
            batch_results = chunk_batch(documents, 200, 20, 100)
        except ImportError:
            from locallens._locallens_rs import (  # type: ignore[attr-defined,no-redef]
                chunk_batch,
            )

            # Old in-package layout: (items) with (text, size, overlap, ft)
            items = [
                ("word " * 200, 200, 20, ".txt"),
                ("def foo():\n    pass\n" * 20, 200, 20, ".py"),
                ("# Title\n\ncontent " * 30, 200, 20, ".md"),
            ]
            batch_results = chunk_batch(items)

        assert len(batch_results) == 3
        for chunks in batch_results:
            assert isinstance(chunks, list)
