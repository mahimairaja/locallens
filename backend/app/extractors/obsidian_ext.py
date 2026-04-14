"""Obsidian vault extractor for .md files inside Obsidian vaults."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")


def _is_obsidian_vault(file_path: Path) -> bool:
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
    return _FRONTMATTER_RE.sub("", text)


def _resolve_wikilinks(text: str) -> str:
    def _replace(m: re.Match) -> str:
        display = m.group(2)
        if display:
            return display
        return m.group(1)
    return _WIKILINK_RE.sub(_replace, text)


class ObsidianExtractor:
    """Extract text from .md files inside Obsidian vaults."""

    extractor_name = "obsidian"

    def can_handle(self, file_path: Path) -> bool:
        return _is_obsidian_vault(file_path)

    def extract(self, file_path: Path) -> str:
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = file_path.read_text(encoding="latin-1")
            except Exception as exc:
                logger.warning("Could not read %s: %s", file_path, exc)
                return ""
        except Exception as exc:
            logger.warning("Could not read %s: %s", file_path, exc)
            return ""

        text = _strip_frontmatter(text)
        text = _resolve_wikilinks(text)
        return text
