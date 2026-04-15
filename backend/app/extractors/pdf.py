"""PDF extractor using pymupdf (fitz), with optional Tesseract OCR fallback."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image

    _ocr_available = True
except ImportError:
    _ocr_available = False


class PdfExtractor:
    """Extract text from .pdf files using pymupdf, falling back to OCR."""

    extractor_name = "pymupdf"

    def extract(self, file_path: Path) -> str:
        """Concatenate text from all pages of the PDF."""
        try:
            import fitz

            doc = fitz.open(file_path)
            pages = [page.get_text() for page in doc]
            doc.close()
            text = "\n".join(pages)

            if self._needs_ocr(text, len(pages)):
                ocr_text = self._ocr_extract(file_path)
                if ocr_text:
                    self.extractor_name = "ocr_tesseract"
                    return ocr_text

            return text
        except Exception as exc:
            logger.warning("Could not extract PDF %s: %s", file_path, exc)
            return ""

    def extract_with_pages(self, file_path: Path) -> tuple[str, list[int]]:
        """Extract text with page boundary character offsets."""
        try:
            import fitz

            doc = fitz.open(file_path)
            pages = [page.get_text() for page in doc]
            num_pages = len(pages)
            doc.close()

            full_text = "\n".join(pages)

            if self._needs_ocr(full_text, num_pages):
                ocr_pages = self._ocr_extract_pages(file_path)
                if ocr_pages:
                    pages = ocr_pages
                    full_text = "\n".join(pages)
                    self.extractor_name = "ocr_tesseract"

            offsets = []
            offset = 0
            for page_text in pages:
                offsets.append(offset)
                offset += len(page_text) + 1

            return full_text, offsets
        except Exception as exc:
            logger.warning("Could not extract PDF %s: %s", file_path, exc)
            return "", []

    def _needs_ocr(self, text: str, num_pages: int) -> bool:
        if num_pages == 0:
            return False
        return len(text.strip()) / num_pages < 50

    def _ocr_extract(self, file_path: Path) -> str:
        if not _ocr_available:
            return ""
        pages = self._ocr_extract_pages(file_path)
        if pages:
            logger.warning("OCR fallback activated for %s", file_path)
            return "\n".join(pages)
        return ""

    def _ocr_extract_pages(self, file_path: Path) -> list[str]:
        if not _ocr_available:
            return []
        try:
            import fitz

            doc = fitz.open(file_path)
            pages = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img)
                pages.append(page_text)
            doc.close()
            return pages
        except Exception as exc:
            logger.warning("OCR failed for %s: %s", file_path, exc)
            return []
