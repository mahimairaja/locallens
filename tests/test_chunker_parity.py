"""Parity tests: Rust chunker vs Python chunker.

Skipped when the Rust extension is not available.
"""

import pytest

from locallens._rust import HAS_RUST_CHUNKER

pytestmark = pytest.mark.skipif(
    not HAS_RUST_CHUNKER, reason="Rust chunker not available"
)


def _python_chunk_text(text: str, size: int, overlap: int, file_type: str) -> list[str]:
    """Call the Python chunker directly, bypassing the Rust dispatch."""
    from locallens.chunker import (
        _chunk_code,
        _chunk_markdown,
        _chunk_paragraphs,
        _chunk_spreadsheet,
        _subdivide,
    )

    if not text or not text.strip():
        return []

    ft = file_type.lower()
    if ft in (".md", ".txt"):
        return _chunk_markdown(text, size, overlap)
    elif ft in (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb"):
        return _chunk_code(text, size, overlap)
    elif ft in (".pdf", ".docx", ".pptx", ".html"):
        return _chunk_paragraphs(text, size, overlap)
    elif ft in (".xlsx", ".xls", ".csv", ".tsv"):
        return _chunk_spreadsheet(text, size, overlap)
    else:
        return _subdivide(text, size, overlap)


def _rust_chunk_text(text: str, size: int, overlap: int, file_type: str) -> list[str]:
    from locallens._locallens_rs import chunk_text

    return chunk_text(text, size, overlap, file_type)


class TestSubdivideParity:
    def test_simple_text(self):
        text = "word " * 300
        py = _python_chunk_text(text, 200, 20, ".xyz")
        rs = _rust_chunk_text(text, 200, 20, ".xyz")
        assert len(rs) == pytest.approx(len(py), abs=len(py) * 0.1)

    def test_empty(self):
        assert _rust_chunk_text("", 1000, 50, "") == []
        assert _rust_chunk_text("   ", 1000, 50, ".md") == []

    def test_short_text_dropped(self):
        text = "short"
        py = _python_chunk_text(text, 1000, 50, ".txt")
        rs = _rust_chunk_text(text, 1000, 50, ".txt")
        assert py == rs == []


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
        from locallens._locallens_rs import chunk_batch

        items = [
            ("word " * 200, 200, 20, ".txt"),
            ("def foo():\n    pass\n" * 20, 200, 20, ".py"),
            ("# Title\n\ncontent " * 30, 200, 20, ".md"),
        ]
        batch_results = chunk_batch(items)
        for i, (text, size, overlap, ft) in enumerate(items):
            sequential = _rust_chunk_text(text, size, overlap, ft)
            assert batch_results[i] == sequential
