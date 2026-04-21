"""Filesystem watcher: auto-indexes new/modified files, removes deleted ones.

Runs as a background thread started on FastAPI startup. Monitors all folders
that have been previously indexed (tracked in watched_folders.json).
"""

import json
import logging
import threading
from datetime import UTC
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

logger = logging.getLogger(__name__)

_WATCHED_FILE = Path.home() / ".locallens" / "watched_folders.json"

_observer: BaseObserver | None = None
_watched_folders: set[str] = set()
_event_counts: dict[str, int] = {"created": 0, "modified": 0, "deleted": 0}
_lock = threading.Lock()


class _IndexHandler(FileSystemEventHandler):
    """Re-index on create/modify, remove on delete."""

    def __init__(self, folder: str):
        self.folder = folder

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self._handle_change(str(event.src_path), "created")

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self._handle_change(str(event.src_path), "modified")

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            return
        with _lock:
            _event_counts["deleted"] += 1
        try:
            from app.services import store

            store.ensure_collection()
            store.delete_by_file(str(Path(str(event.src_path)).resolve()))
            logger.info("Watcher: removed points for deleted file %s", event.src_path)
        except Exception as exc:
            logger.warning("Watcher: delete failed for %s: %s", event.src_path, exc)

    def _handle_change(self, file_path: str, event_type: str):
        from app.config import settings

        path = Path(file_path)
        supported = {ext.strip() for ext in settings.supported_extensions.split(",")}
        if path.suffix.lower() not in supported:
            return
        if any(part.startswith(".") for part in path.parts):
            return
        if not path.is_file():
            return

        with _lock:
            _event_counts[event_type] += 1

        try:
            # Re-index just the parent to pick up the changed file
            # Use force=True since the file content changed
            logger.info("Watcher: re-indexing %s (%s)", path.name, event_type)

            # Quick single-file re-index
            _reindex_single_file(path)
        except Exception as exc:
            logger.warning("Watcher: reindex failed for %s: %s", file_path, exc)


def _reindex_single_file(file_path: Path):
    """Re-index a single file."""
    import uuid
    from datetime import datetime

    from qdrant_client.models import PointStruct

    from app.config import settings
    from app.extractors import get_extractor
    from app.services import bm25, embedder, store
    from locallens._internals._file_core import hash_file
    from locallens.pipeline.chunker import chunk_text

    UUID_NAMESPACE = uuid.UUID("d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a")

    extractor = get_extractor(file_path.suffix.lower(), file_path=file_path)
    if not extractor:
        return

    # Delete old points first
    abs_path = str(file_path.resolve())
    store.delete_by_file(abs_path)

    text = extractor.extract(file_path)
    if not text or not text.strip():
        return

    fhash = hash_file(file_path)

    extractor_name = getattr(extractor, "extractor_name", "unknown")
    chunks = chunk_text(
        text,
        settings.chunk_size,
        settings.chunk_overlap,
        file_type=file_path.suffix.lower(),
    )
    if not chunks:
        return

    embeddings = embedder.encode(chunks)
    now = datetime.now(UTC).isoformat()

    try:
        file_mtime = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=UTC
        ).isoformat()
    except OSError:
        file_mtime = None

    points = [
        PointStruct(
            id=str(uuid.uuid5(UUID_NAMESPACE, f"{abs_path}:{i}")),
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
                "page_number": None,
                "file_modified_at": file_mtime,
            },
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]

    store.upsert_chunks(points)
    bm25.add_documents(
        [
            {
                "id": str(uuid.uuid5(UUID_NAMESPACE, f"{abs_path}:{i}")),
                "chunk_text": chunk,
            }
            for i, chunk in enumerate(chunks)
        ]
    )


def load_watched_folders() -> set[str]:
    """Load watched folders from disk."""
    if _WATCHED_FILE.exists():
        try:
            return set(json.loads(_WATCHED_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_watched_folders():
    """Save current watched folders to disk."""
    _WATCHED_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WATCHED_FILE.write_text(json.dumps(list(_watched_folders)))


def add_folder(folder: str) -> None:
    """Start watching a folder."""
    global _observer
    _watched_folders.add(folder)
    save_watched_folders()

    if _observer is not None and _observer.is_alive():
        _observer.schedule(_IndexHandler(folder), folder, recursive=True)
        logger.info("Watcher: now watching %s", folder)


def remove_folder(folder: str) -> None:
    """Stop watching a folder."""
    _watched_folders.discard(folder)
    save_watched_folders()
    # Full restart needed to actually unschedule — simplified approach
    restart()


def start() -> None:
    """Start the filesystem watcher in a background thread."""
    global _observer, _watched_folders

    _watched_folders = load_watched_folders()
    if not _watched_folders:
        logger.info("Watcher: no folders to watch")
        return

    _observer = Observer()
    for folder in _watched_folders:
        if Path(folder).is_dir():
            _observer.schedule(_IndexHandler(folder), folder, recursive=True)
            logger.info("Watcher: watching %s", folder)
        else:
            logger.warning("Watcher: folder not found, skipping: %s", folder)

    _observer.daemon = True
    _observer.start()
    logger.info("Watcher: started with %d folders", len(_watched_folders))


def stop() -> None:
    """Stop the watcher."""
    global _observer
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=5)
        _observer = None


def restart() -> None:
    """Restart with current folder set."""
    stop()
    start()


def get_status() -> dict:
    """Return watcher status."""
    return {
        "running": _observer is not None and _observer.is_alive()
        if _observer
        else False,
        "folders": list(_watched_folders),
        "event_counts": dict(_event_counts),
    }
