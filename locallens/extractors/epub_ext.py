"""EPUB extractor using ebooklib."""

from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()

try:
    import ebooklib  # noqa: F401
    from ebooklib import epub as _epub_mod  # noqa: F401

    _ebooklib_available = True
except ImportError:
    _ebooklib_available = False


class EpubExtractor(LocalLensExtractor):
    """Extract chapter text from .epub files using ebooklib."""

    def supported_extensions(self) -> list[str]:
        if _ebooklib_available:
            return [".epub"]
        return []

    def name(self) -> str:
        return "epub"

    def extract(self, file_path: Path) -> str:
        if not _ebooklib_available:
            console.print(
                f"[yellow]Warning: ebooklib not installed, cannot extract {file_path}[/yellow]"
            )
            return ""
        try:
            import io
            from html.parser import HTMLParser

            from ebooklib import ITEM_DOCUMENT, epub

            book = epub.read_epub(str(file_path), options={"ignore_ncx": True})

            # Simple HTML-to-text parser
            class _HTMLToText(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self._buf = io.StringIO()

                def handle_data(self, data):
                    self._buf.write(data)

                def get_text(self) -> str:
                    return self._buf.getvalue()

            sections: list[str] = []
            for item in book.get_items_of_type(ITEM_DOCUMENT):
                content = item.get_content()
                if not content:
                    continue
                parser = _HTMLToText()
                try:
                    html_text = content.decode("utf-8", errors="replace")
                except AttributeError:
                    html_text = str(content)
                parser.feed(html_text)
                text = parser.get_text().strip()
                if text:
                    # Use the item file name as a chapter title hint
                    chapter_title = (
                        Path(item.get_name()).stem.replace("_", " ").replace("-", " ")
                    )
                    sections.append(f"## {chapter_title}\n\n{text}")

            return "\n\n".join(sections)
        except Exception as exc:
            console.print(
                f"[yellow]Warning: Could not extract EPUB {file_path}: {exc}[/yellow]"
            )
            return ""
