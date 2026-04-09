"""DOCX extractor using python-docx."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocxExtractor:
    """Extract text from .docx files using python-docx."""

    def extract(self, file_path: Path) -> str:
        """Concatenate all paragraph text from the document."""
        try:
            from docx import Document

            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception as exc:
            logger.warning("Could not extract DOCX %s: %s", file_path, exc)
            return ""
