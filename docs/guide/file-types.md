# Supported File Types

## Documents

| Extension | Extractor | Optional Dependency | Notes |
|---|---|---|---|
| `.txt` | TextExtractor | — | Plain text |
| `.md` | TextExtractor | — | Markdown (structure-aware chunking) |
| `.pdf` | PdfExtractor | — | Uses PyMuPDF |
| `.docx` | DocxExtractor | — | Microsoft Word |
| `.html` | TextExtractor | — | HTML (tags stripped) |

## Code

| Extension | Extractor | Optional Dependency | Notes |
|---|---|---|---|
| `.py` | CodeExtractor | — | Python |
| `.js` | CodeExtractor | — | JavaScript |
| `.ts` | CodeExtractor | — | TypeScript |
| `.go` | CodeExtractor | — | Go |
| `.rs` | CodeExtractor | — | Rust |
| `.java` | CodeExtractor | — | Java |
| `.c` | CodeExtractor | — | C |
| `.cpp` | CodeExtractor | — | C++ |
| `.rb` | CodeExtractor | — | Ruby |

## Data

| Extension | Extractor | Optional Dependency | Notes |
|---|---|---|---|
| `.csv` | SpreadsheetExtractor | — | Comma-separated values |
| `.tsv` | SpreadsheetExtractor | — | Tab-separated values |
| `.xlsx` | SpreadsheetExtractor | `locallens[parsing]` | Excel (requires openpyxl) |
| `.xls` | SpreadsheetExtractor | `locallens[parsing]` | Legacy Excel |
| `.pptx` | LiteParseExtractor | `locallens[parsing]` | PowerPoint (requires liteparse) |

## Email

| Extension | Extractor | Optional Dependency | Notes |
|---|---|---|---|
| `.eml` | EmailExtractor | `locallens[email]` | Standard email format |
| `.msg` | EmailExtractor | `locallens[email]` | Outlook message format |

## Books

| Extension | Extractor | Optional Dependency | Notes |
|---|---|---|---|
| `.epub` | EpubExtractor | `locallens[ebooks]` | EPUB e-books |

## Adding a custom extractor

LocalLens uses Python entry points for extractor plugins. Create a class that extends `LocalLensExtractor`:

```python
from pathlib import Path
from locallens.extractors.base import LocalLensExtractor

class MyExtractor(LocalLensExtractor):
    def supported_extensions(self) -> list[str]:
        return [".xyz"]

    def name(self) -> str:
        return "my-extractor"

    def extract(self, file_path: Path) -> str:
        return file_path.read_text()
```

Register it as an entry point in your package's `pyproject.toml`:

```toml
[project.entry-points."locallens.extractors"]
my_extractor = "my_package.extractor:MyExtractor"
```
