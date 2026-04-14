"""DOCX extractor using python-docx."""

from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()


class DocxExtractor(LocalLensExtractor):
    """Extract text from .docx files using python-docx."""

    def supported_extensions(self) -> list[str]:
        return [".docx"]

    def name(self) -> str:
        return "python-docx"

    def extract(self, file_path: Path) -> str:
        """Concatenate all paragraph text from the document."""
        try:
            from docx import Document

            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not extract DOCX {file_path}: {exc}[/yellow]")
            return ""
