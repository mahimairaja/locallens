//! File system watcher using `notify` with crossbeam-channel event queue.
//!
//! Wraps `notify-debouncer-full` to provide debounced file system events
//! with a poll-based Python API. Events accumulate in a crossbeam channel
//! and are drained by `poll_events()`.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use crossbeam_channel::{Receiver, Sender};
use notify::RecursiveMode;
use notify_debouncer_full::{new_debouncer, DebounceEventResult, Debouncer, RecommendedCache};
use pyo3::prelude::*;

use locallens_core::WatchEvent;

type WatcherInner = Debouncer<notify::RecommendedWatcher, RecommendedCache>;

fn now_timestamp() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// A file system watcher backed by OS-native APIs (FSEvents, inotify,
/// ReadDirectoryChangesW) with configurable debounce. Uses a crossbeam
/// channel for the event queue instead of Arc<Mutex<Vec>>.
#[pyclass(module = "locallens_core")]
pub struct FileWatcher {
    roots: Vec<PathBuf>,
    debounce_ms: u64,
    sender: Sender<WatchEvent>,
    receiver: Receiver<WatchEvent>,
    running: Arc<AtomicBool>,
    watcher: Option<WatcherInner>,
}

#[pymethods]
impl FileWatcher {
    #[new]
    #[pyo3(signature = (roots, *, debounce_ms=500))]
    fn new(roots: Vec<PathBuf>, debounce_ms: u64) -> Self {
        let (sender, receiver) = crossbeam_channel::unbounded();
        Self {
            roots,
            debounce_ms,
            sender,
            receiver,
            running: Arc::new(AtomicBool::new(false)),
            watcher: None,
        }
    }

    /// Start watching all configured roots recursively.
    fn start(&mut self) -> PyResult<()> {
        if self.running.load(Ordering::Relaxed) {
            return Ok(());
        }

        let sender = self.sender.clone();
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
                        let ts = now_timestamp();
                        for event in debounced_events {
                            let kind = match event.kind {
                                notify::EventKind::Create(_) => "created",
                                notify::EventKind::Modify(_) => "modified",
                                notify::EventKind::Remove(_) => "deleted",
                                _ => continue,
                            };
                            for path in &event.paths {
                                if let Some(s) = path.to_str() {
                                    let _ = sender.send(WatchEvent {
                                        event_type: kind.to_string(),
                                        path: s.to_string(),
                                        timestamp: ts,
                                    });
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

        // Watch each root; clean up on failure
        if let Some(ref mut w) = self.watcher {
            for root in &self.roots {
                if let Err(e) = w.watch(root, RecursiveMode::Recursive) {
                    self.running.store(false, Ordering::Relaxed);
                    self.watcher = None;
                    return Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
                        "watch {}: {e}",
                        root.display()
                    )));
                }
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

    /// Drain all pending events from the channel.
    /// Returns a list of `WatchEvent` objects with event_type, path, and
    /// timestamp fields.
    fn poll_events(&self) -> Vec<WatchEvent> {
        let mut events = Vec::new();
        while let Ok(event) = self.receiver.try_recv() {
            events.push(event);
        }
        events
    }

    /// Check whether the watcher is currently running.
    fn is_running(&self) -> bool {
        self.running.load(Ordering::Relaxed)
    }

    /// Return the list of watched folder paths.
    fn watched_folders(&self) -> Vec<String> {
        self.roots
            .iter()
            .map(|p| p.to_string_lossy().into_owned())
            .collect()
    }

    fn __enter__(mut slf: PyRefMut<'_, Self>) -> PyResult<PyRefMut<'_, Self>> {
        slf.start()?;
        Ok(slf)
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

impl Drop for FileWatcher {
    fn drop(&mut self) {
        self.running.store(false, Ordering::Relaxed);
        self.watcher = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn watcher_lifecycle() {
        let dir = tempfile::tempdir().unwrap();
        let mut w = FileWatcher::new(vec![dir.path().to_path_buf()], 100);

        assert!(!w.is_running());

        // Start watching
        w.start().unwrap();
        assert!(w.is_running());

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

        // Verify event fields are populated
        let first = &events[0];
        assert!(!first.event_type.is_empty());
        assert!(!first.path.is_empty());
        assert!(first.timestamp > 0.0);

        // Stop
        w.stop().unwrap();
        assert!(!w.is_running());
    }

    #[test]
    fn poll_events_drains_channel() {
        let dir = tempfile::tempdir().unwrap();
        let mut w = FileWatcher::new(vec![dir.path().to_path_buf()], 100);
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

    #[test]
    fn watched_folders_returns_roots() {
        let dir = tempfile::tempdir().unwrap();
        let w = FileWatcher::new(vec![dir.path().to_path_buf()], 100);
        let folders = w.watched_folders();
        assert_eq!(folders.len(), 1);
        assert_eq!(folders[0], dir.path().to_string_lossy().to_string());
    }

    #[test]
    fn drop_cleans_up() {
        let dir = tempfile::tempdir().unwrap();
        let running;
        {
            let mut w = FileWatcher::new(vec![dir.path().to_path_buf()], 100);
            w.start().unwrap();
            running = Arc::clone(&w.running);
            assert!(running.load(Ordering::Relaxed));
            // w is dropped here
        }
        assert!(!running.load(Ordering::Relaxed));
    }
}
