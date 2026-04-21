"""Tests for the Rust file watcher and the unified FileWatcher wrapper.

Skipped when the Rust watcher extension is not available.
"""

import tempfile
import time
from pathlib import Path

import pytest

from locallens._internals._rust import HAS_RUST_WATCHER

pytestmark = pytest.mark.skipif(
    not HAS_RUST_WATCHER, reason="Rust watcher not available"
)


def _rust_watcher_cls():
    """Return the Rust watcher class, trying both layouts.

    - New workspace (`locallens_core`) exports `FileWatcher`
    - Old in-package (`locallens._locallens_rs`) exports `RustWatcher`
    """
    try:
        from locallens_core import FileWatcher  # type: ignore[import-not-found]

        return FileWatcher
    except ImportError:
        pass
    try:
        from locallens._locallens_rs import RustWatcher  # type: ignore[import-not-found]

        return RustWatcher
    except ImportError:
        pytest.skip("Rust watcher class not importable")


def _normalize(events):
    """Normalize events to [(path, kind), ...] regardless of backend."""
    if not events:
        return []
    if hasattr(events[0], "path"):
        return [(e.path, e.event_type) for e in events]
    return list(events)


class TestRustWatcherDirect:
    """Test the Rust watcher pyclass directly."""

    def test_start_stop(self):
        WatcherCls = _rust_watcher_cls()
        with tempfile.TemporaryDirectory() as d:
            w = WatcherCls([Path(d)], debounce_ms=100)
            w.start()
            w.stop()

    def test_poll_events_returns_list(self):
        WatcherCls = _rust_watcher_cls()
        with tempfile.TemporaryDirectory() as d:
            w = WatcherCls([Path(d)], debounce_ms=100)
            w.start()
            events = w.poll_events()
            assert isinstance(events, list)
            w.stop()

    def test_detects_file_creation(self):
        WatcherCls = _rust_watcher_cls()
        with tempfile.TemporaryDirectory() as d:
            w = WatcherCls([Path(d)], debounce_ms=100)
            w.start()

            Path(d, "test.txt").write_text("hello")
            time.sleep(0.5)

            events = _normalize(w.poll_events())
            paths = [p for p, _ in events]
            assert any("test.txt" in p for p in paths), (
                f"Expected test.txt in events: {events}"
            )

            w.stop()

    def test_detects_file_deletion(self):
        WatcherCls = _rust_watcher_cls()
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "del.txt")
            f.write_text("bye")
            time.sleep(0.1)

            w = WatcherCls([Path(d)], debounce_ms=100)
            w.start()
            time.sleep(0.1)

            f.unlink()
            time.sleep(0.5)

            events = _normalize(w.poll_events())
            del_events = [k for p, k in events if "del.txt" in p]
            # macOS FSEvents may report deletion as "modified"; Linux
            # inotify reports "deleted". Accept either for del.txt.
            assert len(del_events) > 0, f"Expected event for del.txt, got: {events}"

            w.stop()

    def test_poll_drains_queue(self):
        WatcherCls = _rust_watcher_cls()
        with tempfile.TemporaryDirectory() as d:
            w = WatcherCls([Path(d)], debounce_ms=100)
            w.start()

            Path(d, "a.txt").write_text("aaa")
            time.sleep(0.5)

            first = w.poll_events()
            second = w.poll_events()

            assert len(first) > 0
            assert len(second) == 0

            w.stop()


class TestFileWatcherWrapper:
    """Test the unified FileWatcher from locallens/_internals/_watcher.py."""

    def test_context_manager(self):
        from locallens._internals._watcher import FileWatcher

        with tempfile.TemporaryDirectory() as d:
            with FileWatcher([d], debounce_ms=100) as w:
                assert w.backend == "rust"
                Path(d, "ctx.txt").write_text("context")
                time.sleep(0.5)
                events = w.poll_events()
                assert isinstance(events, list)

    def test_backend_is_rust(self):
        from locallens._internals._watcher import FileWatcher

        with tempfile.TemporaryDirectory() as d:
            with FileWatcher([d]) as w:
                assert w.backend == "rust"
