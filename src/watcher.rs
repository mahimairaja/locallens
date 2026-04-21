//! Rust file system watcher using the `notify` crate.
//!
//! Wraps `notify-debouncer-full` to provide debounced file system events
//! with a poll-based Python API. Events accumulate in a thread-safe queue
//! and are drained by `poll_events()`.
//!
//! Falls back to Python watchdog when the Rust extension is not available
//! (see `locallens/_watcher.py`).

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use notify::RecursiveMode;
use notify_debouncer_full::{new_debouncer, DebounceEventResult, Debouncer, RecommendedCache};
use pyo3::prelude::*;

type WatcherInner = Debouncer<notify::RecommendedWatcher, RecommendedCache>;

/// A file system watcher backed by OS-native APIs (FSEvents, inotify,
/// ReadDirectoryChangesW) with configurable debounce.
#[pyclass(module = "locallens._locallens_rs")]
pub struct RustWatcher {
    roots: Vec<PathBuf>,
    debounce_ms: u64,
    events: Arc<Mutex<Vec<(String, String)>>>,
    running: Arc<AtomicBool>,
    #[allow(dead_code)]
    watcher: Option<WatcherInner>,
}

#[pymethods]
impl RustWatcher {
    #[new]
    #[pyo3(signature = (roots, *, debounce_ms=500))]
    fn new(roots: Vec<PathBuf>, debounce_ms: u64) -> Self {
        Self {
            roots,
            debounce_ms,
            events: Arc::new(Mutex::new(Vec::new())),
            running: Arc::new(AtomicBool::new(false)),
            watcher: None,
        }
    }

    /// Start watching all configured roots recursively.
    fn start(&mut self) -> PyResult<()> {
        if self.running.load(Ordering::Relaxed) {
            return Ok(());
        }

        let events = Arc::clone(&self.events);
        let running = Arc::clone(&self.running);

        let debouncer = new_debouncer(
            Duration::from_millis(self.debounce_ms),
            None,
            move |result: DebounceEventResult| {
                if !running.load(Ordering::Relaxed) {
                    return;
                }
                match result {
                    Ok(debounced_events) => {
                        let mut queue = events.lock().unwrap();
                        for event in debounced_events {
                            let kind = match event.kind {
                                notify::EventKind::Create(_) => "created",
                                notify::EventKind::Modify(_) => "modified",
                                notify::EventKind::Remove(_) => "deleted",
                                _ => continue,
                            };
                            for path in &event.paths {
                                if let Some(s) = path.to_str() {
                                    queue.push((s.to_string(), kind.to_string()));
                                }
                            }
                        }
                    }
                    Err(errors) => {
                        for e in errors {
                            eprintln!("locallens watcher error: {e}");
                        }
                    }
                }
            },
        )
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("watcher init: {e}")))?;

        self.watcher = Some(debouncer);
        self.running.store(true, Ordering::Relaxed);

        // Watch each root
        if let Some(ref mut w) = self.watcher {
            for root in &self.roots {
                w.watch(root, RecursiveMode::Recursive).map_err(|e| {
                    pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "watch {}: {e}",
                        root.display()
                    ))
                })?;
            }
        }

        Ok(())
    }

    /// Stop watching and clean up.
    fn stop(&mut self) -> PyResult<()> {
        self.running.store(false, Ordering::Relaxed);
        // Dropping the debouncer stops the background thread.
        self.watcher = None;
        Ok(())
    }

    /// Drain all pending events. Returns a list of ``(path, kind)`` tuples
    /// where kind is ``"created"``, ``"modified"``, or ``"deleted"``.
    fn poll_events(&self) -> Vec<(String, String)> {
        let mut queue = self.events.lock().unwrap();
        std::mem::take(&mut *queue)
    }

    fn __enter__(&mut self) -> PyResult<()> {
        self.start()
    }

    #[pyo3(signature = (exc_type=None, exc_val=None, exc_tb=None))]
    fn __exit__(
        &mut self,
        exc_type: Option<&Bound<'_, PyAny>>,
        exc_val: Option<&Bound<'_, PyAny>>,
        exc_tb: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<bool> {
        let _ = (exc_type, exc_val, exc_tb);
        self.stop()?;
        Ok(false) // Don't suppress exceptions
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn watcher_lifecycle() {
        let dir = tempfile::tempdir().unwrap();
        let mut w = RustWatcher::new(vec![dir.path().to_path_buf()], 100);

        // Start watching
        w.start().unwrap();
        assert!(w.running.load(Ordering::Relaxed));

        // Create a file
        fs::write(dir.path().join("test.txt"), "hello").unwrap();

        // Give the debouncer time to fire
        std::thread::sleep(Duration::from_millis(300));

        let events = w.poll_events();
        // We should have at least one event (created or modified)
        // Note: exact event count varies by OS
        assert!(
            !events.is_empty(),
            "expected at least one event after file creation"
        );

        // Stop
        w.stop().unwrap();
        assert!(!w.running.load(Ordering::Relaxed));
    }

    #[test]
    fn poll_events_drains_queue() {
        let dir = tempfile::tempdir().unwrap();
        let mut w = RustWatcher::new(vec![dir.path().to_path_buf()], 100);
        w.start().unwrap();

        fs::write(dir.path().join("a.txt"), "aaa").unwrap();
        std::thread::sleep(Duration::from_millis(300));

        let first = w.poll_events();
        let second = w.poll_events();

        // First poll should have events, second should be empty (drained)
        assert!(!first.is_empty());
        assert!(second.is_empty());

        w.stop().unwrap();
    }
}
