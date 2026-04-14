"""PDF extractor using pymupdf (fitz), with optional Tesseract OCR fallback."""

from pathlib import Path

from rich.console import Console

from locallens.extractors.base import LocalLensExtractor

console = Console()

try:
    import pytesseract
    from PIL import Image
    _ocr_available = True
except ImportError:
    _ocr_available = False


class PdfExtractor(LocalLensExtractor):
    """Extract text from .pdf files using pymupdf, falling back to OCR."""

    _extractor_name = "pymupdf"

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def name(self) -> str:
        return self._extractor_name

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
                    self._extractor_name = "ocr_tesseract"
                    return ocr_text

            return text
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not extract PDF {file_path}: {exc}[/yellow]")
            return ""

    # Keep extractor_name as a dynamic property for legacy compat
    @property
    def extractor_name(self) -> str:
        return self._extractor_name

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
                    self._extractor_name = "ocr_tesseract"

            offsets = []
            offset = 0
            for page_text in pages:
                offsets.append(offset)
                offset += len(page_text) + 1

            return full_text, offsets
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not extract PDF {file_path}: {exc}[/yellow]")
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
            console.print(f"[yellow]OCR fallback activated for {file_path}[/yellow]")
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
            console.print(f"[yellow]Warning: OCR failed for {file_path}: {exc}[/yellow]")
            return []
