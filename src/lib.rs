//! LocalLens native extension entry point.
//!
//! Exposes the BM25 index class, the file walker / parallel SHA-256
//! hasher, the structure-aware text chunker, and the file system
//! watcher. Each module advertises a `HAS_*` boolean so that
//! `locallens/_rust.py` can branch accurately.

use pyo3::prelude::*;

mod bm25;
mod chunker;
mod walk;
mod watcher;

#[pymodule]
#[pyo3(name = "_locallens_rs")]
fn locallens_rs(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("HAS_BM25", true)?;
    m.add("HAS_CHUNKER", true)?;
    m.add("HAS_WALKER", true)?;
    m.add("HAS_WATCHER", true)?;
    m.add_class::<bm25::RustBM25>()?;
    m.add_class::<walk::RustWalker>()?;
    m.add_class::<watcher::RustWatcher>()?;
    m.add_function(wrap_pyfunction!(chunker::chunk_text, m)?)?;
    m.add_function(wrap_pyfunction!(chunker::chunk_batch, m)?)?;
    Ok(())
}
