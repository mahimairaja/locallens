"""Extractor registry: maps file extensions to extractor instances."""

from locallens.extractors.base import BaseExtractor
from locallens.extractors.text import TextExtractor
from locallens.extractors.pdf import PdfExtractor
from locallens.extractors.docx_ext import DocxExtractor
from locallens.extractors.code import CodeExtractor

_REGISTRY: dict[str, BaseExtractor] = {}

_text_ext = TextExtractor()
for ext in (".txt", ".md"):
    _REGISTRY[ext] = _text_ext

_REGISTRY[".pdf"] = PdfExtractor()
_REGISTRY[".docx"] = DocxExtractor()

_code_ext = CodeExtractor()
for ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb"):
    _REGISTRY[ext] = _code_ext


def get_extractor(extension: str) -> BaseExtractor | None:
    """Return the appropriate extractor for the given file extension, or None."""
    return _REGISTRY.get(extension)
