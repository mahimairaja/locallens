"""Structure-aware text chunking with overlap, respecting boundaries.

Used by both the CLI (locallens/) and backend (imported or duplicated).

Adaptive chunking rules:
- Markdown/text: split on heading boundaries (# lines), then subdivide large sections
- Code: split on function/class boundaries (def, class, function, fn, func)
- PDF/docx: split on paragraph boundaries (double newlines)
- Spreadsheet: each sheet is one chunk unless >1000 chars, then split by row groups
- Max chunk 1000 chars, min 100 chars, 50 char overlap within sections
"""

import re

MAX_CHUNK = 1000
MIN_CHUNK = 100
OVERLAP = 50

# Patterns for structure-aware splitting
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_CODE_BOUNDARY_RE = re.compile(
    r"^(?:def |class |function |fn |func |export function |export default function |async function )",
    re.MULTILINE,
)
_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def _subdivide(text: str, max_size: int, overlap: int) -> list[str]:
    """Simple char-based subdivision with word-boundary respect."""
    if not text or not text.strip():
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + max_size
        if end < text_len:
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK:
            chunks.append(chunk)

        start = max(start + 1, end - overlap)

    return chunks


def _split_by_pattern(text: str, pattern: re.Pattern) -> list[str]:
    """Split text at regex match positions, keeping each match with the section that follows it."""
    positions = [m.start() for m in pattern.finditer(text)]
    if not positions:
        return [text]

    sections = []
    # Text before first match
    if positions[0] > 0:
        pre = text[:positions[0]].strip()
        if pre:
            sections.append(pre)

    for i, pos in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        section = text[pos:end].strip()
        if section:
            sections.append(section)

    return sections


def chunk_text(text: str, size: int = MAX_CHUNK, overlap: int = OVERLAP, file_type: str = "") -> list[str]:
    """Structure-aware chunking. Falls back to simple subdivision for unknown types.

    Args:
        text: Full document text.
        size: Target max chunk size (default 1000).
        overlap: Overlap chars when subdividing within a section (default 50).
        file_type: File extension like ".md", ".py", ".pdf" for structure hints.
    """
    if not text or not text.strip():
        return []

    ft = file_type.lower()

    if ft in (".md", ".txt"):
        return _chunk_markdown(text, size, overlap)
    elif ft in (".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb"):
        return _chunk_code(text, size, overlap)
    elif ft in (".pdf", ".docx", ".pptx", ".html"):
        return _chunk_paragraphs(text, size, overlap)
    elif ft in (".xlsx", ".xls", ".csv", ".tsv"):
        return _chunk_spreadsheet(text, size, overlap)
    else:
        return _subdivide(text, size, overlap)


def _chunk_markdown(text: str, size: int, overlap: int) -> list[str]:
    """Split on heading boundaries, then subdivide large sections."""
    sections = _split_by_pattern(text, _HEADING_RE)
    chunks = []
    for section in sections:
        if len(section) <= size:
            if len(section) >= MIN_CHUNK:
                chunks.append(section)
        else:
            chunks.extend(_subdivide(section, size, overlap))
    return chunks


def _chunk_code(text: str, size: int, overlap: int) -> list[str]:
    """Split on function/class boundaries, then subdivide."""
    sections = _split_by_pattern(text, _CODE_BOUNDARY_RE)
    chunks = []
    for section in sections:
        if len(section) <= size:
            if len(section) >= MIN_CHUNK:
                chunks.append(section)
        else:
            chunks.extend(_subdivide(section, size, overlap))
    return chunks


def _chunk_paragraphs(text: str, size: int, overlap: int) -> list[str]:
    """Split on paragraph boundaries (double newlines), keep tables whole when possible."""
    paragraphs = _PARAGRAPH_RE.split(text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if not current:
            current = para
        elif len(current) + len(para) + 2 <= size:
            current += "\n\n" + para
        else:
            if len(current) >= MIN_CHUNK:
                chunks.append(current)
            elif chunks:
                # Merge tiny paragraphs with previous chunk
                chunks[-1] += "\n\n" + current
            current = para

    if current:
        if len(current) >= MIN_CHUNK:
            chunks.append(current)
        elif chunks:
            chunks[-1] += "\n\n" + current

    # Subdivide any oversized chunks
    final = []
    for chunk in chunks:
        if len(chunk) > size:
            final.extend(_subdivide(chunk, size, overlap))
        else:
            final.append(chunk)

    return final


def _chunk_spreadsheet(text: str, size: int, overlap: int) -> list[str]:
    """Each sheet is one chunk unless >1000 chars, then split by row groups."""
    sheet_blocks = re.split(r"(?=^Sheet: )", text, flags=re.MULTILINE)
    chunks = []
    for block in sheet_blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) <= size:
            if len(block) >= MIN_CHUNK:
                chunks.append(block)
        else:
            # Split by row groups
            lines = block.split("\n")
            current = ""
            for line in lines:
                if not current:
                    current = line
                elif len(current) + len(line) + 1 <= size:
                    current += "\n" + line
                else:
                    if len(current) >= MIN_CHUNK:
                        chunks.append(current)
                    current = line
            if current and len(current) >= MIN_CHUNK:
                chunks.append(current)
    return chunks
