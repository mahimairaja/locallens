"""EPUB extractor using ebooklib."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import ebooklib  # noqa: F401
    from ebooklib import epub as _epub_mod  # noqa: F401

    _ebooklib_available = True
except ImportError:
    _ebooklib_available = False


class EpubExtractor:
    """Extract chapter text from .epub files using ebooklib."""

    extractor_name = "epub"

    def extract(self, file_path: Path) -> str:
        if not _ebooklib_available:
            logger.warning("ebooklib not installed, cannot extract %s", file_path)
            return ""
        try:
            import io
            from html.parser import HTMLParser

            from ebooklib import ITEM_DOCUMENT, epub

            book = epub.read_epub(str(file_path), options={"ignore_ncx": True})

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
                    chapter_title = (
                        Path(item.get_name()).stem.replace("_", " ").replace("-", " ")
                    )
                    sections.append(f"## {chapter_title}\n\n{text}")

            return "\n\n".join(sections)
        except Exception as exc:
            logger.warning("Could not extract EPUB %s: %s", file_path, exc)
            return ""
