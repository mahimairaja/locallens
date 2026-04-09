"""PDF extractor using pymupdf (fitz)."""

from pathlib import Path

from rich.console import Console

console = Console()


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
            console.print(f"[yellow]Warning: Could not extract PDF {file_path}: {exc}[/yellow]")
            return ""
