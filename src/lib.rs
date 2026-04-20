//! LocalLens native extension entry point.
//!
//! Today this only exposes the BM25 module. Chunker and file-walker modules
//! will be added in follow-up PRs; their `HAS_*` flags stay `false` until the
//! matching module lands so that `locallens/_rust.py` can branch accurately.

use pyo3::prelude::*;

mod bm25;

#[pymodule]
#[pyo3(name = "_locallens_rs")]
fn locallens_rs(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("HAS_BM25", true)?;
    m.add("HAS_CHUNKER", false)?;
    m.add("HAS_WALKER", false)?;
    m.add_class::<bm25::RustBM25>()?;
    Ok(())
}
