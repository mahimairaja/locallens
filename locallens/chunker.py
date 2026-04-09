"""Text chunking with overlap, respecting word boundaries."""


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into chunks of approximately `size` characters with `overlap`.

    Splits respect word boundaries and strips whitespace from each chunk.
    Chunks shorter than 50 characters are discarded.
    """
    if not text or not text.strip():
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + size

        if end < text_len:
            # Walk back to the nearest space to avoid splitting mid-word
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if len(chunk) >= 50:
            chunks.append(chunk)

        # Advance by (end - overlap), but at least 1 character to avoid infinite loop
        start = max(start + 1, end - overlap)

    return chunks
