//! PyO3 entry point that registers all locallens Rust crates into a single
//! Python module `locallens_core`.

use pyo3::prelude::*;

#[pymodule]
fn locallens_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core types
    m.add_class::<locallens_core_types::FileEntry>()?;
    m.add_class::<locallens_core_types::ChunkResult>()?;
    m.add_class::<locallens_core_types::WatchEvent>()?;

    // BM25
    m.add_class::<locallens_bm25::BM25Index>()?;

    // Chunker functions
    m.add_function(wrap_pyfunction!(locallens_chunker::chunk_text, m)?)?;
    m.add_function(wrap_pyfunction!(locallens_chunker::chunk_structured, m)?)?;
    m.add_function(wrap_pyfunction!(locallens_chunker::chunk_batch, m)?)?;
    m.add_function(wrap_pyfunction!(locallens_chunker::supported_languages, m)?)?;

    // Walker functions
    m.add_function(wrap_pyfunction!(locallens_walker::walk_files, m)?)?;
    m.add_function(wrap_pyfunction!(locallens_walker::extract_texts, m)?)?;

    // Watcher
    m.add_class::<locallens_watcher::FileWatcher>()?;

    Ok(())
}
