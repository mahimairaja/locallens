"""Extractor registry: maps file extensions to extractor instances.

Registration order (highest priority first):
1. LiteParse (when installed) — overrides PDF, DOCX, PPTX, XLSX, HTML
2. Built-in extractors (text, pdf, docx, code, spreadsheet, email, epub, obsidian)
3. Third-party plugin extractors discovered via ``locallens.extractors`` entry points
"""

import logging

from rich.console import Console

from locallens.extractors.base import (
    BaseExtractor,
    LocalLensExtractor,
    discover_plugins,
)
from locallens.extractors.code import CodeExtractor
from locallens.extractors.docx_ext import DocxExtractor
from locallens.extractors.pdf import PdfExtractor
from locallens.extractors.spreadsheet import SpreadsheetExtractor
from locallens.extractors.text import TextExtractor

logger = logging.getLogger(__name__)
console = Console()

_REGISTRY: dict[str, LocalLensExtractor | BaseExtractor] = {}

# --- 3. Plugin extractors (lowest priority, registered first so built-ins win) ---
_plugin_extractors = discover_plugins()
for _ext, _inst in _plugin_extractors.items():
    _REGISTRY[_ext] = _inst

# --- 2. Built-in extractors ---
_text_ext = TextExtractor()
for _ext in _text_ext.supported_extensions():
    _REGISTRY[_ext] = _text_ext

_REGISTRY[".pdf"] = PdfExtractor()
_REGISTRY[".docx"] = DocxExtractor()

_code_ext = CodeExtractor()
for _ext in _code_ext.supported_extensions():
    _REGISTRY[_ext] = _code_ext

_spreadsheet_ext = SpreadsheetExtractor()
for _ext in _spreadsheet_ext.supported_extensions():
    _REGISTRY[_ext] = _spreadsheet_ext

# Email extractor (built-in; .msg support requires python-oletools)
try:
    from locallens.extractors.email_ext import EmailExtractor

    _email_ext = EmailExtractor()
    for _ext in _email_ext.supported_extensions():
        _REGISTRY[_ext] = _email_ext
except ImportError:
    pass

# EPUB extractor (requires ebooklib)
try:
    from locallens.extractors.epub_ext import EpubExtractor

    _epub_ext = EpubExtractor()
    for _ext in _epub_ext.supported_extensions():
        _REGISTRY[_ext] = _epub_ext
except ImportError:
    pass

# Obsidian extractor — stored separately; .md dispatch handled in get_extractor()
_obsidian_ext = None
try:
    from locallens.extractors.obsidian_ext import ObsidianExtractor

    _obsidian_ext = ObsidianExtractor()
except ImportError:
    pass

# --- 1. LiteParse (highest priority among built-ins when installed) ---
try:
    from locallens.extractors.liteparse_ext import (
        LiteParseExtractor,
        liteparse_available,
    )

    if liteparse_available:
        _lp = LiteParseExtractor()
        for _ext in _lp.supported_extensions():
            _REGISTRY[_ext] = _lp
        console.print(
            "[dim]LiteParse available — using it for PDF, DOCX, PPTX, XLSX, HTML[/dim]"
        )
except ImportError:
    pass

# Log discovered plugins
if _plugin_extractors:
    for _ext, _inst in _plugin_extractors.items():
        # Only log if the plugin wasn't overridden by a built-in
        if _REGISTRY.get(_ext) is _inst:
            logger.info("Plugin extractor %r handling %s", _inst.name(), _ext)


def get_extractor(
    extension: str, file_path=None
) -> LocalLensExtractor | BaseExtractor | None:
    """Return the appropriate extractor for the given file extension, or None.

    For .md files, checks whether the file is inside an Obsidian vault and
    returns the ObsidianExtractor when appropriate.
    """
    if extension == ".md" and file_path is not None and _obsidian_ext is not None:
        from pathlib import Path

        fp = Path(file_path) if not isinstance(file_path, Path) else file_path
        if _obsidian_ext.can_handle(fp):
            return _obsidian_ext

    return _REGISTRY.get(extension)
