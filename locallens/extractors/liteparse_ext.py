"""LiteParse extractor for .pdf, .docx, .pptx, .xlsx, .html files.

Takes priority over pymupdf and python-docx when liteparse is installed.
Falls back gracefully when not installed.
"""

from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()

try:
    import liteparse

    liteparse_available = True
except ImportError:
    liteparse_available = False


class LiteParseExtractor(LocalLensExtractor):
    """Extract text from documents using LiteParse."""

    def supported_extensions(self) -> list[str]:
        return [".pdf", ".docx", ".pptx", ".xlsx", ".html"]

    def name(self) -> str:
        return "liteparse"

    def extract(self, file_path: Path) -> str:
        """Extract text using liteparse."""
        try:
            result = liteparse.parse(str(file_path))
            return result.text if hasattr(result, "text") else str(result)
        except Exception as exc:
            console.print(
                f"[yellow]Warning: LiteParse failed for {file_path}: {exc}[/yellow]"
            )
            return ""

    def extract_with_pages(self, file_path: Path) -> tuple[str, list[int]]:
        """Extract text with page boundary offsets (for PDFs)."""
        try:
            result = liteparse.parse(str(file_path))
            text = result.text if hasattr(result, "text") else str(result)
            if hasattr(result, "pages") and result.pages:
                pages = [p.text if hasattr(p, "text") else str(p) for p in result.pages]
                offsets = []
                offset = 0
                for page_text in pages:
                    offsets.append(offset)
                    offset += len(page_text) + 1
                return "\n".join(pages), offsets
            return text, []
        except Exception as exc:
            console.print(
                f"[yellow]Warning: LiteParse failed for {file_path}: {exc}[/yellow]"
            )
            return "", []
