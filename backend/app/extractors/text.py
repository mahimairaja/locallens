"""Text extractor for .txt and .md files."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extract plain text from .txt and .md files."""

    def extract(self, file_path: Path) -> str:
        """Read file as UTF-8, falling back to latin-1."""
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return file_path.read_text(encoding="latin-1")
            except Exception as exc:
                logger.warning("Could not read %s: %s", file_path, exc)
                return ""
        except Exception as exc:
            logger.warning("Could not read %s: %s", file_path, exc)
            return ""
