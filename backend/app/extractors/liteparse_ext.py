"""LiteParse extractor for .pdf, .docx, .pptx, .xlsx, .html files.

Takes priority over pymupdf and python-docx when liteparse is installed.
Falls back gracefully when not installed.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import liteparse

    liteparse_available = True
except ImportError:
    liteparse_available = False


class LiteParseExtractor:
    """Extract text from documents using LiteParse."""

    extractor_name = "liteparse"

    def extract(self, file_path: Path) -> str:
        """Extract text using liteparse."""
        try:
            result = liteparse.parse(str(file_path))
            return result.text if hasattr(result, "text") else str(result)
        except Exception as exc:
            logger.warning("LiteParse failed for %s: %s", file_path, exc)
            return ""

    def extract_with_pages(self, file_path: Path) -> tuple[str, list[int]]:
        """Extract text with page boundary offsets (for PDFs)."""
        try:
            result = liteparse.parse(str(file_path))
            text = result.text if hasattr(result, "text") else str(result)
            # LiteParse may provide page info; fall back to no page tracking
            if hasattr(result, "pages") and result.pages:
                pages = [p.text if hasattr(p, "text") else str(p) for p in result.pages]
                offsets = []
                offset = 0
                for page_text in pages:
                    offsets.append(offset)
                    offset += len(page_text) + 1  # +1 for \n join
                return "\n".join(pages), offsets
            return text, []
        except Exception as exc:
            logger.warning("LiteParse failed for %s: %s", file_path, exc)
            return "", []
