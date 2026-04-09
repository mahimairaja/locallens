"""PDF extractor using pymupdf (fitz)."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PdfExtractor:
    """Extract text from .pdf files using pymupdf."""

    def extract(self, file_path: Path) -> str:
        """Concatenate text from all pages of the PDF."""
        try:
            import fitz

            doc = fitz.open(file_path)
            pages = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(pages)
        except Exception as exc:
            logger.warning("Could not extract PDF %s: %s", file_path, exc)
            return ""
