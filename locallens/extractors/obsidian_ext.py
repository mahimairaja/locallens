"""Obsidian vault extractor for .md files inside Obsidian vaults.

Resolves wikilinks [[page]] and strips YAML frontmatter.
Falls back to the regular TextExtractor for .md files outside Obsidian vaults.
"""

import re
from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()

# Regex for YAML frontmatter (--- delimited at start of file)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
# Regex for wikilinks: [[page]] or [[page|display text]]
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")


def _is_obsidian_vault(file_path: Path) -> bool:
    """Check if the .md file is inside a folder tree containing a .obsidian directory."""
    current = file_path.parent
    while True:
        if (current / ".obsidian").is_dir():
            return True
        parent = current.parent
        if parent == current:
            break
        current = parent
    return False


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from the beginning of a markdown file."""
    return _FRONTMATTER_RE.sub("", text)


def _resolve_wikilinks(text: str) -> str:
    """Replace [[page]] with 'page' and [[page|display]] with 'display'."""
    def _replace(m: re.Match) -> str:
        display = m.group(2)
        if display:
            return display
        return m.group(1)
    return _WIKILINK_RE.sub(_replace, text)


class ObsidianExtractor(LocalLensExtractor):
    """Extract text from .md files inside Obsidian vaults.

    Strips YAML frontmatter and resolves wikilinks to plain text.
    Only activates for .md files that live under a directory containing
    a .obsidian folder.
    """

    def supported_extensions(self) -> list[str]:
        return [".md"]

    def name(self) -> str:
        return "obsidian"

    def can_handle(self, file_path: Path) -> bool:
        """Return True only if the file is inside an Obsidian vault."""
        return _is_obsidian_vault(file_path)

    def extract(self, file_path: Path) -> str:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = file_path.read_text(encoding="latin-1")
            except Exception as exc:
                console.print(f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]")
                return ""
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]")
            return ""

        text = _strip_frontmatter(text)
        text = _resolve_wikilinks(text)
        return text
