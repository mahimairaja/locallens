use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[pyclass(module = "locallens_core")]
pub struct FileEntry {
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub file_name: String,
    #[pyo3(get)]
    pub extension: String,
    #[pyo3(get)]
    pub size_bytes: u64,
    #[pyo3(get)]
    pub modified_at: f64,
}

#[pymethods]
impl FileEntry {
    fn __repr__(&self) -> String {
        format!("FileEntry(path={}, size={})", self.path, self.size_bytes)
    }
}

#[derive(Clone, Debug)]
#[pyclass(module = "locallens_core")]
pub struct ChunkResult {
    #[pyo3(get)]
    pub text: String,
    #[pyo3(get)]
    pub start_offset: usize,
    #[pyo3(get)]
    pub end_offset: usize,
}

#[pymethods]
impl ChunkResult {
    fn __repr__(&self) -> String {
        format!(
            "ChunkResult(len={}, {}..{})",
            self.text.len(),
            self.start_offset,
            self.end_offset
        )
    }

}

#[derive(Clone, Debug)]
#[pyclass(module = "locallens_core")]
pub struct WatchEvent {
    #[pyo3(get)]
    pub event_type: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub timestamp: f64,
}

#[pymethods]
impl WatchEvent {
    fn __repr__(&self) -> String {
        format!("WatchEvent(type={}, path={})", self.event_type, self.path)
    }
}
