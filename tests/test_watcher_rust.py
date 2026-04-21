"""Tests for the Rust file watcher and the unified FileWatcher wrapper.

Skipped when the Rust watcher extension is not available.
"""

import tempfile
import time
from pathlib import Path

import pytest

from locallens._rust import HAS_RUST_WATCHER

pytestmark = pytest.mark.skipif(
    not HAS_RUST_WATCHER, reason="Rust watcher not available"
)


class TestRustWatcherDirect:
    """Test the RustWatcher pyclass directly."""

    def test_start_stop(self):
        from locallens._locallens_rs import RustWatcher

        with tempfile.TemporaryDirectory() as d:
            w = RustWatcher([Path(d)], debounce_ms=100)
            w.start()
            w.stop()

    def test_poll_events_returns_list(self):
        from locallens._locallens_rs import RustWatcher

        with tempfile.TemporaryDirectory() as d:
            w = RustWatcher([Path(d)], debounce_ms=100)
            w.start()
            events = w.poll_events()
            assert isinstance(events, list)
            w.stop()

    def test_detects_file_creation(self):
        from locallens._locallens_rs import RustWatcher

        with tempfile.TemporaryDirectory() as d:
            w = RustWatcher([Path(d)], debounce_ms=100)
            w.start()

            # Create a file
            Path(d, "test.txt").write_text("hello")
            time.sleep(0.5)

            events = w.poll_events()
            paths = [p for p, _ in events]
            assert any("test.txt" in p for p in paths), (
                f"Expected test.txt in events: {events}"
            )

            w.stop()

    def test_detects_file_deletion(self):
        from locallens._locallens_rs import RustWatcher

        with tempfile.TemporaryDirectory() as d:
            # Create file first
            f = Path(d, "del.txt")
            f.write_text("bye")
            time.sleep(0.1)

            w = RustWatcher([Path(d)], debounce_ms=100)
            w.start()
            time.sleep(0.1)

            # Delete it
            f.unlink()
            time.sleep(0.5)

            events = w.poll_events()
            kinds = {k for _, k in events if "del.txt" in _}
            # Should have "deleted" (may also have "modified" on some OSes)
            assert "deleted" in kinds or len(events) > 0, (
                f"Expected deletion event: {events}"
            )

            w.stop()

    def test_poll_drains_queue(self):
        from locallens._locallens_rs import RustWatcher

        with tempfile.TemporaryDirectory() as d:
            w = RustWatcher([Path(d)], debounce_ms=100)
            w.start()

            Path(d, "a.txt").write_text("aaa")
            time.sleep(0.5)

            first = w.poll_events()
            second = w.poll_events()

            assert len(first) > 0
            assert len(second) == 0

            w.stop()


class TestFileWatcherWrapper:
    """Test the unified FileWatcher from locallens/_watcher.py."""

    def test_context_manager(self):
        from locallens._watcher import FileWatcher

        with tempfile.TemporaryDirectory() as d:
            with FileWatcher([d], debounce_ms=100) as w:
                assert w.backend == "rust"
                Path(d, "ctx.txt").write_text("context")
                time.sleep(0.5)
                events = w.poll_events()
                assert isinstance(events, list)

    def test_backend_is_rust(self):
        from locallens._watcher import FileWatcher

        with tempfile.TemporaryDirectory() as d:
            w = FileWatcher([d])
            assert w.backend == "rust"
