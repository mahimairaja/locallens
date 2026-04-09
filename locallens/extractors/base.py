"""Base extractor protocol."""

from pathlib import Path
from typing import Protocol


class BaseExtractor(Protocol):
    """Protocol that all file extractors must implement."""

    def extract(self, file_path: Path) -> str:
        """Extract text content from the given file. Return empty string on failure."""
        ...
