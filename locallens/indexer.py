"""File indexer: walk folder, extract, chunk, embed, upsert into Qdrant Edge."""

import hashlib
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from locallens import bm25, store
from locallens.chunker import chunk_text
from locallens.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_FILE_SIZE_MB,
    QDRANT_SYNC_URL,
    SKIP_HIDDEN,
    SUPPORTED_EXTENSIONS,
)
from locallens.embedder import embed_texts
from locallens.extractors import get_extractor

console = Console()

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


def index_folder(folder: Path, force: bool = False) -> None:
    """Index all supported files in the given folder into Qdrant Edge.

    Dedup is per-file via the ``file_hash`` payload index: a single filtered
    ``count`` call per file replaces the old O(n) pre-pass scroll.
    """
    store.init()

    # Collect files to process
    all_files: list[Path] = []
    for file_path in sorted(folder.rglob("*")):
        if not file_path.is_file():
            continue
        if SKIP_HIDDEN and _is_hidden(file_path.relative_to(folder)):
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if file_path.stat().st_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            console.print(
                f"[yellow]Skipping (>{MAX_FILE_SIZE_MB}MB): {file_path}[/yellow]"
            )
            continue
        all_files.append(file_path)

    indexed_files = 0
    total_chunks = 0
    skipped = 0
    start = time.time()

    # Optional push-sync — when QDRANT_SYNC_URL is set, indexed points are
    # dual-written to a remote Qdrant server so the web backend sees them.
    sync_queue: list[dict] | None = [] if QDRANT_SYNC_URL else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing files", total=len(all_files))

        for file_path in all_files:
            progress.update(task, description=f"Indexing {file_path.name}")

            try:
                fhash = _file_hash(file_path)
            except PermissionError:
                console.print(
                    f"[yellow]Warning: Permission denied: {file_path}[/yellow]"
                )
                progress.advance(task)
                continue
            except Exception as exc:
                console.print(
                    f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]"
                )
                progress.advance(task)
                continue

            # O(1) dedup via the file_hash payload index.
            if not force and store.has_hash(fhash):
                skipped += 1
                progress.advance(task)
                continue

            extractor = get_extractor(file_path.suffix.lower(), file_path=file_path)
            if extractor is None:
                progress.advance(task)
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
                progress.advance(task)
                continue

            extractor_name = getattr(extractor, "extractor_name", "unknown")

            chunks = chunk_text(
                text, CHUNK_SIZE, CHUNK_OVERLAP, file_type=file_path.suffix.lower()
            )
            if not chunks:
                progress.advance(task)
                continue

            page_numbers = _assign_page_numbers(text, chunks, page_offsets)
            embeddings = embed_texts(chunks)
            now = datetime.now(UTC).isoformat()
            abs_path = str(file_path.resolve())

            try:
                file_mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=UTC
                ).isoformat()
            except OSError:
                file_mtime = None

            points = [
                {
                    "id": _point_id(abs_path, i),
                    "vector": list(emb) if not isinstance(emb, list) else emb,
                    "payload": {
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
                }
                for i, (chunk, emb, pn) in enumerate(
                    zip(chunks, embeddings, page_numbers)
                )
            ]

            store.upsert_batch(points)
            bm25.add_documents(
                [
                    {"id": _point_id(abs_path, i), "chunk_text": chunk}
                    for i, chunk in enumerate(chunks)
                ]
            )
            if sync_queue is not None:
                sync_queue.extend(points)
            indexed_files += 1
            total_chunks += len(chunks)

            progress.advance(task)

    bm25.flush()

    elapsed = time.time() - start
    console.print(
        f"\n[green]Indexed {indexed_files} files ({total_chunks} chunks) "
        f"in {elapsed:.1f}s. Skipped {skipped} unchanged files.[/green]"
    )

    # Flush push-sync queue at the end of indexing.
    if sync_queue:
        from locallens import sync as _sync

        try:
            pushed = _sync.push(sync_queue)
            console.print(f"[cyan]Synced {pushed} points to {QDRANT_SYNC_URL}[/cyan]")
        except Exception as exc:
            console.print(f"[yellow]Sync failed: {exc}[/yellow]")
