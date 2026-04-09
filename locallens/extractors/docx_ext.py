"""DOCX extractor using python-docx."""

from pathlib import Path

from rich.console import Console

console = Console()


class DocxExtractor:
    """Extract text from .docx files using python-docx."""

    def extract(self, file_path: Path) -> str:
        """Concatenate all paragraph text from the document."""
        try:
            from docx import Document

            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not extract DOCX {file_path}: {exc}[/yellow]")
            return ""
