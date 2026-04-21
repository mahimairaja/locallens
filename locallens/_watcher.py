"""Unified file watcher API.

Uses the Rust ``notify``-backed ``RustWatcher`` when the extension is
available, otherwise falls back to Python ``watchdog``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from locallens._rust import HAS_RUST_WATCHER

if HAS_RUST_WATCHER:
    from locallens._locallens_rs import RustWatcher  # type: ignore[import-not-found]

log = logging.getLogger(__name__)


class FileWatcher:
    """Cross-backend file watcher with debounce.

    Usage::

        watcher = FileWatcher(["/path/to/folder"])
        watcher.start()
        events = watcher.poll_events()  # [(path, "created"/"modified"/"deleted"), ...]
        watcher.stop()

    Or as a context manager::

        with FileWatcher(["/path"]) as w:
            events = w.poll_events()
    """

    def __init__(
        self,
        roots: list[str | Path],
        debounce_ms: int = 500,
    ) -> None:
        self._roots = [str(Path(r).resolve()) for r in roots]
        self._debounce_ms = debounce_ms
        self._backend: str = "rust" if HAS_RUST_WATCHER else "watchdog"
        self._impl: Any = None
        self._running = False

        # Watchdog fallback state
        self._observer: Any = None
        self._events: list[tuple[str, str]] = []

    @property
    def backend(self) -> str:
        """Return ``"rust"`` or ``"watchdog"``."""
        return self._backend

    def start(self) -> None:
        """Begin watching all roots recursively."""
        if self._running:
            return

        if self._backend == "rust":
            self._impl = RustWatcher(
                [Path(r) for r in self._roots],
                debounce_ms=self._debounce_ms,
            )
            self._impl.start()
        else:
            self._start_watchdog()

        self._running = True

    def stop(self) -> None:
        """Stop watching and clean up."""
        if not self._running:
            return

        if self._backend == "rust" and self._impl is not None:
            self._impl.stop()
        elif self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        self._running = False

    def poll_events(self) -> list[tuple[str, str]]:
        """Drain pending events. Returns ``[(path, kind), ...]``."""
        if self._backend == "rust" and self._impl is not None:
            return self._impl.poll_events()
        # Watchdog fallback: drain the accumulated list
        events = list(self._events)
        self._events.clear()
        return events

    def __enter__(self) -> FileWatcher:
        self.start()
        return self

    def __exit__(self, *_args: object) -> bool:
        self.stop()
        return False

    # ── watchdog fallback ───────────────────────────────────────────

    def _start_watchdog(self) -> None:
        try:
            from watchdog.events import (
                FileSystemEvent,
                FileSystemEventHandler,
            )
            from watchdog.observers import Observer
        except ImportError as exc:
            raise ImportError(
                "Neither Rust watcher nor watchdog available. "
                "Install watchdog: pip install locallens[watch]"
            ) from exc

        events_list = self._events

        class _Handler(FileSystemEventHandler):
            def on_created(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    events_list.append((str(event.src_path), "created"))

            def on_modified(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    events_list.append((str(event.src_path), "modified"))

            def on_deleted(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    events_list.append((str(event.src_path), "deleted"))

        handler = _Handler()
        observer = Observer()
        for root in self._roots:
            observer.schedule(handler, root, recursive=True)
        observer.start()
        self._observer = observer
