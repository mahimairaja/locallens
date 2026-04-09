"""File indexer: walk folder, extract, chunk, embed, upsert into Qdrant."""

import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client.models import PointStruct
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

from locallens.chunker import chunk_text
from locallens.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_FILE_SIZE_MB,
    SKIP_HIDDEN,
    SUPPORTED_EXTENSIONS,
)
from locallens.embedder import embed_texts
from locallens.extractors import get_extractor
from locallens import store

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


def index_folder(folder: Path, force: bool = False) -> None:
    """Index all supported files in the given folder into Qdrant."""
    store.init()

    # Gather existing hashes for dedup
    existing_hashes: set[str] = set() if force else store.get_all_hashes()

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
            console.print(f"[yellow]Skipping (>10MB): {file_path}[/yellow]")
            continue
        all_files.append(file_path)

    indexed_files = 0
    total_chunks = 0
    skipped = 0
    start = time.time()

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
                console.print(f"[yellow]Warning: Permission denied: {file_path}[/yellow]")
                progress.advance(task)
                continue
            except Exception as exc:
                console.print(f"[yellow]Warning: Could not read {file_path}: {exc}[/yellow]")
                progress.advance(task)
                continue

            if not force and fhash in existing_hashes:
                skipped += 1
                progress.advance(task)
                continue

            extractor = get_extractor(file_path.suffix.lower())
            if extractor is None:
                progress.advance(task)
                continue

            text = extractor.extract(file_path)
            if not text or not text.strip():
                progress.advance(task)
                continue

            chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            if not chunks:
                progress.advance(task)
                continue

            embeddings = embed_texts(chunks)
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

            store.upsert_batch(points)
            indexed_files += 1
            total_chunks += len(chunks)
            existing_hashes.add(fhash)

            progress.advance(task)

    elapsed = time.time() - start
    console.print(
        f"\n[green]Indexed {indexed_files} files ({total_chunks} chunks) "
        f"in {elapsed:.1f}s. Skipped {skipped} unchanged files.[/green]"
    )
