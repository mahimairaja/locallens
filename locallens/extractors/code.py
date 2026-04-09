"""Code extractor for source code files."""

from pathlib import Path

from rich.console import Console

console = Console()


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
                console.print(f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]")
                return ""
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]")
            return ""
