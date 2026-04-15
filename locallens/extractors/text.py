"""Text extractor for .txt and .md files."""

from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()


class TextExtractor(LocalLensExtractor):
    """Extract plain text from .txt and .md files."""

    def supported_extensions(self) -> list[str]:
        return [".txt", ".md"]

    def name(self) -> str:
        return "text"

    def extract(self, file_path: Path) -> str:
        """Read file as UTF-8, falling back to latin-1."""
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return file_path.read_text(encoding="latin-1")
            except Exception as exc:
                console.print(
                    f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]"
                )
                return ""
        except Exception as exc:
            console.print(
                f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]"
            )
            return ""
