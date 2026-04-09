"""File indexing service: walk folder, extract, chunk, embed, upsert into Qdrant."""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from qdrant_client.models import PointStruct

from app.config import settings
from app.extractors import get_extractor
from app.models import IndexProgress
from app.services import embedder, store

logger = logging.getLogger(__name__)

UUID_NAMESPACE = uuid.UUID("d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a")


def _is_hidden(path: Path) -> bool:
    """Check if any component of the path starts with a dot."""
    return any(part.startswith(".") for part in path.parts)


def _file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file content."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _point_id(file_path: str, chunk_index: int) -> str:
    """Generate a deterministic UUID5 from file_path + chunk_index."""
    return str(uuid.uuid5(UUID_NAMESPACE, f"{file_path}:{chunk_index}"))


def _chunk_text(text: str, size: int, overlap: int) -> list[str]:
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


def _get_supported_extensions() -> set[str]:
    """Parse the comma-separated supported_extensions setting into a set."""
    return {ext.strip() for ext in settings.supported_extensions.split(",")}


def index_folder(
    folder_path: str,
    force: bool = False,
    progress_callback: Optional[Callable[[IndexProgress], None]] = None,
) -> IndexProgress:
    """Index all supported files in the given folder into Qdrant.

    Args:
        folder_path: Absolute path to the folder to index.
        force: If True, re-index all files regardless of hash.
        progress_callback: Optional callable invoked with IndexProgress updates.

    Returns:
        Final IndexProgress with status "done" or "error".
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        error_progress = IndexProgress(
            status="error",
            error=f"Folder not found: {folder_path}",
        )
        if progress_callback:
            progress_callback(error_progress)
        return error_progress

    store.ensure_collection()
    supported = _get_supported_extensions()
    max_bytes = settings.max_file_size_mb * 1024 * 1024

    # Gather existing hashes for dedup
    existing_hashes: set[str] = set() if force else store.get_all_hashes()

    # Scan for supported files
    progress = IndexProgress(status="scanning")
    if progress_callback:
        progress_callback(progress)

    all_files: list[Path] = []
    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue
        if _is_hidden(file_path.relative_to(folder)):
            continue
        if file_path.suffix.lower() not in supported:
            continue
        if file_path.stat().st_size > max_bytes:
            logger.warning("Skipping (>%dMB): %s", settings.max_file_size_mb, file_path)
            continue
        all_files.append(file_path)

    start = time.time()
    files_processed = 0
    chunks_created = 0

    progress = IndexProgress(
        status="indexing",
        files_total=len(all_files),
    )
    if progress_callback:
        progress_callback(progress)

    for file_path in all_files:
        try:
            fhash = _file_hash(file_path)
        except (PermissionError, OSError) as exc:
            logger.warning("Could not read %s: %s", file_path, exc)
            files_processed += 1
            continue

        if not force and fhash in existing_hashes:
            files_processed += 1
            progress = IndexProgress(
                status="indexing",
                current_file=file_path.name,
                files_processed=files_processed,
                files_total=len(all_files),
                chunks_created=chunks_created,
                elapsed_seconds=round(time.time() - start, 1),
            )
            if progress_callback:
                progress_callback(progress)
            continue

        extractor = get_extractor(file_path.suffix.lower())
        if extractor is None:
            files_processed += 1
            continue

        text = extractor.extract(file_path)
        if not text or not text.strip():
            files_processed += 1
            continue

        chunks = _chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            files_processed += 1
            continue

        embeddings = embedder.encode(chunks)
        now = datetime.now(timezone.utc).isoformat()
        abs_path = str(file_path.resolve())

        points = [
            PointStruct(
                id=_point_id(abs_path, i),
                vector=emb,
                payload={
                    "file_path": abs_path,
                    "file_name": file_path.name,
                    "file_type": file_path.suffix.lower(),
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "file_hash": fhash,
                    "indexed_at": now,
                },
            )
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]

        store.upsert_chunks(points)
        chunks_created += len(chunks)
        existing_hashes.add(fhash)
        files_processed += 1

        progress = IndexProgress(
            status="indexing",
            current_file=file_path.name,
            files_processed=files_processed,
            files_total=len(all_files),
            chunks_created=chunks_created,
            elapsed_seconds=round(time.time() - start, 1),
        )
        if progress_callback:
            progress_callback(progress)

    elapsed = round(time.time() - start, 1)
    final_progress = IndexProgress(
        status="done",
        files_processed=files_processed,
        files_total=len(all_files),
        chunks_created=chunks_created,
        elapsed_seconds=elapsed,
    )
    if progress_callback:
        progress_callback(final_progress)

    logger.info(
        "Indexed %d files (%d chunks) in %.1fs",
        files_processed,
        chunks_created,
        elapsed,
    )
    return final_progress
