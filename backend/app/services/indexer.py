"""File indexing service: walk folder, extract, chunk, embed, upsert into Qdrant."""

import logging
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client.models import PointStruct

from app.config import settings
from app.extractors import get_extractor
from app.models import IndexProgress
from app.services import bm25, embedder, store
from locallens._file_core import hash_file as _file_hash  # re-export
from locallens._file_core import walk_and_hash

logger = logging.getLogger(__name__)

UUID_NAMESPACE = uuid.UUID("d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a")

__all__ = ["index_folder", "_file_hash"]


def _point_id(file_path: str, chunk_index: int) -> str:
    """Generate a deterministic UUID5 from file_path + chunk_index."""
    return str(uuid.uuid5(UUID_NAMESPACE, f"{file_path}:{chunk_index}"))


def _chunk_text(text: str, size: int, overlap: int, file_type: str = "") -> list[str]:
    """Structure-aware chunking. Delegates to the shared chunker module."""
    from locallens.chunker import chunk_text as _adaptive_chunk

    return _adaptive_chunk(text, size, overlap, file_type)


def _page_for_offset(char_offset: int, page_offsets: list[int]) -> int:
    """Given a character offset, return the 1-based page number."""
    page = 1
    for i, po in enumerate(page_offsets):
        if char_offset >= po:
            page = i + 1
        else:
            break
    return page


def _assign_page_numbers(
    text: str,
    chunks: list[str],
    page_offsets: list[int] | None,
) -> list[int | None]:
    """Map each chunk to its approximate page number."""
    if not page_offsets:
        return [None] * len(chunks)

    result: list[int | None] = []
    search_start = 0
    for chunk in chunks:
        idx = text.find(chunk[:80], search_start)
        if idx == -1:
            idx = search_start
        result.append(_page_for_offset(idx, page_offsets))
        search_start = idx
    return result


def _get_supported_extensions() -> set[str]:
    """Parse the comma-separated supported_extensions setting into a set."""
    return {ext.strip() for ext in settings.supported_extensions.split(",")}


def index_folder(
    folder_path: str,
    force: bool = False,
    progress_callback: Callable[[IndexProgress], None] | None = None,
    collection: str | None = None,
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

    store.ensure_collection(collection)
    supported = _get_supported_extensions()
    max_bytes = settings.max_file_size_mb * 1024 * 1024

    # Gather existing hashes for dedup
    existing_hashes: set[str] = (
        set() if force else store.get_all_hashes(collection=collection)
    )

    # Scan for supported files
    progress = IndexProgress(status="scanning")
    if progress_callback:
        progress_callback(progress)

    # Walk + hash in one pass — parallel SHA-256 via Rust when
    # HAS_RUST_WALKER is True. See locallens/_file_core.py.
    entries = walk_and_hash(
        folder,
        frozenset(supported),
        max_file_size_bytes=max_bytes,
        skip_hidden=True,
    )

    start = time.time()
    files_processed = 0
    chunks_created = 0
    files_new = 0
    files_updated = 0
    files_skipped = 0

    progress = IndexProgress(
        status="indexing",
        files_total=len(entries),
    )
    if progress_callback:
        progress_callback(progress)

    for entry in entries:
        file_path = entry.path
        fhash = entry.sha256

        if not force and fhash in existing_hashes:
            files_processed += 1
            files_skipped += 1
            progress = IndexProgress(
                status="indexing",
                current_file=file_path.name,
                files_processed=files_processed,
                files_total=len(entries),
                chunks_created=chunks_created,
                elapsed_seconds=round(time.time() - start, 1),
                files_new=files_new,
                files_updated=files_updated,
                files_skipped=files_skipped,
            )
            if progress_callback:
                progress_callback(progress)
            continue

        extractor = get_extractor(file_path.suffix.lower(), file_path=file_path)
        if extractor is None:
            files_processed += 1
            continue

        # Extract text, with page tracking for PDFs
        page_offsets = None
        if (
            hasattr(extractor, "extract_with_pages")
            and file_path.suffix.lower() == ".pdf"
        ):
            text, page_offsets = extractor.extract_with_pages(file_path)
        else:
            text = extractor.extract(file_path)

        if not text or not text.strip():
            files_processed += 1
            continue

        extractor_name = getattr(extractor, "extractor_name", "unknown")

        chunks = _chunk_text(
            text,
            settings.chunk_size,
            settings.chunk_overlap,
            file_type=file_path.suffix.lower(),
        )
        if not chunks:
            files_processed += 1
            continue

        page_numbers = _assign_page_numbers(text, chunks, page_offsets)
        embeddings = embedder.encode(chunks)
        now = datetime.now(UTC).isoformat()
        abs_path = str(file_path.resolve())

        # File modification time for date-range filtering
        try:
            file_mtime = datetime.fromtimestamp(
                file_path.stat().st_mtime, tz=UTC
            ).isoformat()
        except OSError:
            file_mtime = None

        points = [
            PointStruct(
                id=_point_id(abs_path, i),
                vector={settings.vector_name: emb},
                payload={
                    "file_path": abs_path,
                    "file_name": file_path.name,
                    "file_type": file_path.suffix.lower(),
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "file_hash": fhash,
                    "indexed_at": now,
                    "extractor": extractor_name,
                    "page_number": pn,
                    "file_modified_at": file_mtime,
                },
            )
            for i, (chunk, emb, pn) in enumerate(zip(chunks, embeddings, page_numbers))
        ]

        store.upsert_chunks(points, collection=collection)
        bm25.add_documents(
            [
                {"id": _point_id(abs_path, i), "chunk_text": chunk}
                for i, chunk in enumerate(chunks)
            ]
        )
        chunks_created += len(chunks)
        if fhash in existing_hashes:
            files_updated += 1
        else:
            files_new += 1
        existing_hashes.add(fhash)
        files_processed += 1

        progress = IndexProgress(
            status="indexing",
            current_file=file_path.name,
            files_processed=files_processed,
            files_total=len(entries),
            chunks_created=chunks_created,
            elapsed_seconds=round(time.time() - start, 1),
            files_new=files_new,
            files_updated=files_updated,
            files_skipped=files_skipped,
        )
        if progress_callback:
            progress_callback(progress)

    elapsed = round(time.time() - start, 1)
    final_progress = IndexProgress(
        status="done",
        files_processed=files_processed,
        files_total=len(entries),
        chunks_created=chunks_created,
        elapsed_seconds=elapsed,
        files_new=files_new,
        files_updated=files_updated,
        files_skipped=files_skipped,
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
