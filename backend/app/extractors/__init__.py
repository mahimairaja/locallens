"""Extractor registry: maps file extensions to extractor instances."""

import logging
from pathlib import Path
from typing import Protocol

from app.extractors.code import CodeExtractor
from app.extractors.docx_ext import DocxExtractor
from app.extractors.pdf import PdfExtractor
from app.extractors.spreadsheet import SpreadsheetExtractor
from app.extractors.text import TextExtractor

logger = logging.getLogger(__name__)


class BaseExtractor(Protocol):
    """Protocol that all file extractors must implement."""

    extractor_name: str

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

_spreadsheet_ext = SpreadsheetExtractor()
for _ext in (".xlsx", ".xls", ".csv", ".tsv"):
    _REGISTRY[_ext] = _spreadsheet_ext

# Email extractor (.eml always; .msg when oletools installed)
try:
    from app.extractors.email_ext import EmailExtractor

    _email_ext = EmailExtractor()
    _REGISTRY[".eml"] = _email_ext
    # .msg support depends on oletools being installed
    try:
        from oletools import oleobj  # noqa: F401

        _REGISTRY[".msg"] = _email_ext
    except ImportError:
        pass
except ImportError:
    pass

# EPUB extractor (requires ebooklib)
try:
    from app.extractors.epub_ext import EpubExtractor, _ebooklib_available

    if _ebooklib_available:
        _REGISTRY[".epub"] = EpubExtractor()
except ImportError:
    pass

# Obsidian extractor — stored separately; .md dispatch handled in get_extractor()
_obsidian_ext = None
try:
    from app.extractors.obsidian_ext import ObsidianExtractor

    _obsidian_ext = ObsidianExtractor()
except ImportError:
    pass

# LiteParse takes priority when installed
try:
    from app.extractors.liteparse_ext import LiteParseExtractor, liteparse_available

    if liteparse_available:
        _lp = LiteParseExtractor()
        for _ext in (".pdf", ".docx", ".pptx", ".xlsx", ".html"):
            _REGISTRY[_ext] = _lp
        logger.info("LiteParse available — using it for PDF, DOCX, PPTX, XLSX, HTML")
except ImportError:
    pass


def get_extractor(extension: str, file_path=None) -> BaseExtractor | None:
    """Return the appropriate extractor for the given file extension, or None.

    For .md files, checks whether the file is inside an Obsidian vault and
    returns the ObsidianExtractor when appropriate.
    """
    if extension == ".md" and file_path is not None and _obsidian_ext is not None:
        fp = Path(file_path) if not isinstance(file_path, Path) else file_path
        if _obsidian_ext.can_handle(fp):
            return _obsidian_ext

    return _REGISTRY.get(extension)
