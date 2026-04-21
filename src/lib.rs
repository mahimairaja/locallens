//! LocalLens native extension entry point.
//!
//! Exposes the BM25 index class and the file walker / parallel SHA-256
//! hasher. Chunker is reserved for a future PR; its `HAS_CHUNKER` flag
//! stays `false` until the matching module lands so that
//! `locallens/_rust.py` can branch accurately.

use pyo3::prelude::*;

mod bm25;
mod walk;

#[pymodule]
#[pyo3(name = "_locallens_rs")]
fn locallens_rs(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("HAS_BM25", true)?;
    m.add("HAS_CHUNKER", false)?;
    m.add("HAS_WALKER", true)?;
    m.add_class::<bm25::RustBM25>()?;
    m.add_class::<walk::RustWalker>()?;
    Ok(())
}
