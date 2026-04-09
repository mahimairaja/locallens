"""Code extractor for source code files."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeExtractor:
    """Extract source code as plain text, prepending the filename."""

    def extract(self, file_path: Path) -> str:
        """Read source code file as text, prepending a header comment."""
        try:
            content = file_path.read_text(encoding="utf-8")
            return f"# File: {file_path.name}\n{content}"
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="latin-1")
                return f"# File: {file_path.name}\n{content}"
            except Exception as exc:
                logger.warning("Could not read %s: %s", file_path, exc)
                return ""
        except Exception as exc:
            logger.warning("Could not read %s: %s", file_path, exc)
            return ""
