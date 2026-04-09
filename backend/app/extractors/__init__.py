"""Extractor registry: maps file extensions to extractor instances."""

from pathlib import Path
from typing import Protocol

from app.extractors.text import TextExtractor
from app.extractors.pdf import PdfExtractor
from app.extractors.docx_ext import DocxExtractor
from app.extractors.code import CodeExtractor


class BaseExtractor(Protocol):
    """Protocol that all file extractors must implement."""

    def extract(self, file_path: Path) -> str: ...


_REGISTRY: dict[str, BaseExtractor] = {}

_text_ext = TextExtractor()
for _ext in (".txt", ".md"):
    _REGISTRY[_ext] = _text_ext

_REGISTRY[".pdf"] = PdfExtractor()
_REGISTRY[".docx"] = DocxExtractor()

_code_ext = CodeExtractor()
for _ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb"):
    _REGISTRY[_ext] = _code_ext


def get_extractor(extension: str) -> BaseExtractor | None:
    """Return the appropriate extractor for the given file extension, or None."""
    return _REGISTRY.get(extension)
