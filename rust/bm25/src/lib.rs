//! Rust BM25 index for LocalLens.
//!
//! Ranking semantics match `rank_bm25.BM25Okapi` exactly (same `k1=1.5`,
//! `b=0.75`, epsilon-smoothed IDF). The on-disk JSON shape is identical
//! to the Python implementation so a user who switches between a
//! wheel-with-Rust and a wheel-without-Rust install never loses their
//! index.
//!
//! An additional bincode format (.bm25bin) is available via the `save`
//! and `load_bin` static methods for faster serialization.

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::OnceLock;

use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use regex::Regex;
use serde::{Deserialize, Serialize};

fn tokenizer() -> &'static Regex {
    static TOKENIZER: OnceLock<Regex> = OnceLock::new();
    TOKENIZER.get_or_init(|| Regex::new(r"\w+").unwrap())
}

fn tokenize(text: &str) -> Vec<String> {
    let lower = text.to_lowercase();
    tokenizer()
        .find_iter(&lower)
        .map(|m| m.as_str().to_string())
        .collect()
}

/// On-disk payload (JSON). Same shape as the Python `_save_now`.
#[derive(Serialize, Deserialize)]
struct PersistedState {
    doc_ids: Vec<String>,
    corpus_texts: Vec<String>,
}

/// Full state for bincode serialization (.bm25bin format).
#[derive(Serialize, Deserialize)]
struct BincodeState {
    doc_ids: Vec<String>,
    corpus_texts: Vec<String>,
    doc_tf: Vec<HashMap<String, u32>>,
    doc_lengths: Vec<usize>,
    df: HashMap<String, u32>,
    total_tokens: u64,
}

#[pyclass(module = "locallens_core")]
pub struct BM25Index {
    persist_path: PathBuf,
    k1: f64,
    b: f64,
    epsilon: f64,

    doc_ids: Vec<String>,
    id_to_idx: HashMap<String, usize>,
    doc_tf: Vec<HashMap<String, u32>>,
    doc_lengths: Vec<usize>,
    corpus_texts: Vec<String>,
    df: HashMap<String, u32>,
    total_tokens: u64,
    idf: Option<HashMap<String, f64>>,

    dirty: bool,
    atexit_registered: bool,
}

#[pymethods]
impl BM25Index {
    #[new]
    #[pyo3(signature = (persist_path, *, k1 = 1.5, b = 0.75, epsilon = 0.25))]
    fn new(persist_path: PathBuf, k1: f64, b: f64, epsilon: f64) -> Self {
        Self {
            persist_path,
            k1,
            b,
            epsilon,
            doc_ids: Vec::new(),
            id_to_idx: HashMap::new(),
            doc_tf: Vec::new(),
            doc_lengths: Vec::new(),
            corpus_texts: Vec::new(),
            df: HashMap::new(),
            total_tokens: 0,
            idf: None,
            dirty: false,
            atexit_registered: false,
        }
    }

    /// Rebuild from scratch using Python dicts. Eagerly persists.
    fn build_index(&mut self, py: Python<'_>, documents: Vec<Bound<'_, PyDict>>) -> PyResult<()> {
        let parsed = parse_documents(&documents)?;
        py.allow_threads(|| {
            self.reset_state();
            for (id, text) in parsed {
                self.add_internal(id, text);
            }
            self.idf = None;
            self.save_now()
        })?;
        self.dirty = false;
        Ok(())
    }

    /// Rebuild from scratch using (id, text) tuples. Eagerly persists.
    #[pyo3(signature = (documents))]
    fn build(&mut self, py: Python<'_>, documents: Vec<(String, String)>) -> PyResult<()> {
        py.allow_threads(|| {
            self.reset_state();
            for (id, text) in documents {
                self.add_internal(id, text);
            }
            self.idf = None;
            self.save_now()
        })?;
        self.dirty = false;
        Ok(())
    }

    /// Append or in-place update documents. Defers write by default.
    fn add_documents(
        &mut self,
        py: Python<'_>,
        documents: Vec<Bound<'_, PyDict>>,
    ) -> PyResult<()> {
        if documents.is_empty() {
            return Ok(());
        }
        let parsed = parse_documents(&documents)?;
        py.allow_threads(|| {
            for (id, text) in parsed {
                self.add_internal(id, text);
            }
            self.idf = None;
        });
        self.mark_dirty(py)
    }

    /// Remove documents by id. Defers write by default.
    fn remove_documents(&mut self, py: Python<'_>, doc_ids: Vec<String>) -> PyResult<()> {
        if doc_ids.is_empty() {
            return Ok(());
        }
        let removed_any = py.allow_threads(|| self.remove_internal(doc_ids));
        if removed_any {
            self.mark_dirty(py)
        } else {
            Ok(())
        }
    }

    /// Top-k search. Matches `_Bm25Index.search` ordering and scores.
    #[pyo3(signature = (query, top_k = 10))]
    fn search(
        &mut self,
        py: Python<'_>,
        query: &str,
        top_k: usize,
    ) -> PyResult<Vec<(String, f64)>> {
        if self.doc_ids.is_empty() {
            return Ok(Vec::new());
        }
        let tokens = tokenize(query);
        if tokens.is_empty() {
            return Ok(Vec::new());
        }
        Ok(py.allow_threads(|| self.search_internal(&tokens, top_k)))
    }

    /// Load persisted index from JSON. Tolerates missing file (first run).
    fn load(&mut self, py: Python<'_>) -> PyResult<()> {
        if !self.persist_path.exists() {
            return Ok(());
        }
        let raw = fs::read_to_string(&self.persist_path)
            .map_err(|e| PyIOError::new_err(format!("read bm25 index: {e}")))?;
        let parsed: PersistedState = match serde_json::from_str(&raw) {
            Ok(p) => p,
            Err(_) => return Ok(()),
        };
        if parsed.doc_ids.len() != parsed.corpus_texts.len() {
            return Ok(());
        }
        py.allow_threads(|| {
            self.reset_state();
            for (id, text) in parsed.doc_ids.into_iter().zip(parsed.corpus_texts) {
                self.add_internal(id, text);
            }
            self.idf = None;
        });
        self.dirty = false;
        Ok(())
    }

    fn is_loaded(&self) -> bool {
        !self.doc_ids.is_empty()
    }

    /// Number of documents in the index.
    #[getter]
    fn doc_count(&self) -> usize {
        self.doc_ids.len()
    }

    /// Persist pending changes (JSON). Idempotent.
    fn flush(&mut self, py: Python<'_>) -> PyResult<()> {
        if !self.dirty {
            return Ok(());
        }
        py.allow_threads(|| self.save_now())?;
        self.dirty = false;
        Ok(())
    }

    /// Change the on-disk location, flushing pending writes to the old path.
    fn set_persist_path(&mut self, py: Python<'_>, path: PathBuf) -> PyResult<()> {
        self.flush(py)?;
        self.persist_path = path;
        Ok(())
    }

    #[getter]
    fn persist_path(&self) -> PathBuf {
        self.persist_path.clone()
    }

    /// Save to a bincode file (.bm25bin) for faster serialization.
    #[staticmethod]
    #[pyo3(signature = (index, path))]
    fn save(index: &BM25Index, path: PathBuf) -> PyResult<()> {
        let state = BincodeState {
            doc_ids: index.doc_ids.clone(),
            corpus_texts: index.corpus_texts.clone(),
            doc_tf: index.doc_tf.clone(),
            doc_lengths: index.doc_lengths.clone(),
            df: index.df.clone(),
            total_tokens: index.total_tokens,
        };
        let encoded = bincode::serialize(&state)
            .map_err(|e| PyIOError::new_err(format!("serialize bm25 bincode: {e}")))?;
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)
                .map_err(|e| PyIOError::new_err(format!("create bm25 dir: {e}")))?;
        }
        let mut tmp = path.clone();
        let new_ext = match tmp.extension() {
            Some(ext) => {
                let mut s = ext.to_os_string();
                s.push(".tmp");
                s
            }
            None => std::ffi::OsString::from("tmp"),
        };
        tmp.set_extension(new_ext);
        fs::write(&tmp, encoded)
            .map_err(|e| PyIOError::new_err(format!("write bm25 bincode tmp: {e}")))?;
        fs::rename(&tmp, &path)
            .map_err(|e| PyIOError::new_err(format!("rename bm25 bincode: {e}")))?;
        Ok(())
    }

    /// Load from a bincode file (.bm25bin). Returns a new BM25Index.
    #[staticmethod]
    #[pyo3(signature = (path, *, k1 = 1.5, b = 0.75, epsilon = 0.25))]
    fn load_bin(path: PathBuf, k1: f64, b: f64, epsilon: f64) -> PyResult<Self> {
        let raw = fs::read(&path)
            .map_err(|e| PyIOError::new_err(format!("read bm25 bincode: {e}")))?;
        let state: BincodeState = bincode::deserialize(&raw)
            .map_err(|e| PyIOError::new_err(format!("deserialize bm25 bincode: {e}")))?;

        let id_to_idx: HashMap<String, usize> = state
            .doc_ids
            .iter()
            .enumerate()
            .map(|(i, id)| (id.clone(), i))
            .collect();

        Ok(Self {
            persist_path: path.with_extension("json"),
            k1,
            b,
            epsilon,
            doc_ids: state.doc_ids,
            id_to_idx,
            doc_tf: state.doc_tf,
            doc_lengths: state.doc_lengths,
            corpus_texts: state.corpus_texts,
            df: state.df,
            total_tokens: state.total_tokens,
            idf: None,
            dirty: false,
            atexit_registered: false,
        })
    }
}

// ----- pure-Rust helpers (no pyo3 types on the signatures) -----

impl BM25Index {
    fn reset_state(&mut self) {
        self.doc_ids.clear();
        self.id_to_idx.clear();
        self.doc_tf.clear();
        self.doc_lengths.clear();
        self.corpus_texts.clear();
        self.df.clear();
        self.total_tokens = 0;
        self.idf = None;
    }

    /// Delta updates to df / total_tokens.
    fn add_internal(&mut self, doc_id: String, text: String) {
        let tokens = tokenize(&text);
        let length = tokens.len();

        let mut tf: HashMap<String, u32> = HashMap::with_capacity(tokens.len());
        for t in &tokens {
            *tf.entry(t.clone()).or_insert(0) += 1;
        }

        if let Some(&existing) = self.id_to_idx.get(&doc_id) {
            // Subtract old contribution.
            let old_tf = &self.doc_tf[existing];
            self.total_tokens -= self.doc_lengths[existing] as u64;
            let old_terms: Vec<String> = old_tf.keys().cloned().collect();
            for term in old_terms {
                if let Some(count) = self.df.get_mut(&term) {
                    *count -= 1;
                    if *count == 0 {
                        self.df.remove(&term);
                    }
                }
            }
            self.doc_tf[existing] = tf.clone();
            self.doc_lengths[existing] = length;
            self.corpus_texts[existing] = text;
        } else {
            self.id_to_idx.insert(doc_id.clone(), self.doc_ids.len());
            self.doc_ids.push(doc_id);
            self.doc_tf.push(tf.clone());
            self.doc_lengths.push(length);
            self.corpus_texts.push(text);
        }

        self.total_tokens += length as u64;
        for term in tf.keys() {
            *self.df.entry(term.clone()).or_insert(0) += 1;
        }
    }

    /// In-place decrement + compaction. Returns true if at least one doc was removed.
    fn remove_internal(&mut self, doc_ids: Vec<String>) -> bool {
        let id_set: std::collections::HashSet<String> = doc_ids.into_iter().collect();
        let drop_idx: Vec<usize> = self
            .doc_ids
            .iter()
            .enumerate()
            .filter_map(|(i, did)| if id_set.contains(did) { Some(i) } else { None })
            .collect();
        if drop_idx.is_empty() {
            return false;
        }

        for &i in &drop_idx {
            self.total_tokens -= self.doc_lengths[i] as u64;
            let terms: Vec<String> = self.doc_tf[i].keys().cloned().collect();
            for term in terms {
                if let Some(c) = self.df.get_mut(&term) {
                    *c -= 1;
                    if *c == 0 {
                        self.df.remove(&term);
                    }
                }
            }
        }

        let drop_set: std::collections::HashSet<usize> = drop_idx.into_iter().collect();
        self.doc_ids = std::mem::take(&mut self.doc_ids)
            .into_iter()
            .enumerate()
            .filter_map(|(i, v)| if drop_set.contains(&i) { None } else { Some(v) })
            .collect();
        self.doc_tf = std::mem::take(&mut self.doc_tf)
            .into_iter()
            .enumerate()
            .filter_map(|(i, v)| if drop_set.contains(&i) { None } else { Some(v) })
            .collect();
        self.doc_lengths = std::mem::take(&mut self.doc_lengths)
            .into_iter()
            .enumerate()
            .filter_map(|(i, v)| if drop_set.contains(&i) { None } else { Some(v) })
            .collect();
        self.corpus_texts = std::mem::take(&mut self.corpus_texts)
            .into_iter()
            .enumerate()
            .filter_map(|(i, v)| if drop_set.contains(&i) { None } else { Some(v) })
            .collect();
        self.id_to_idx = self
            .doc_ids
            .iter()
            .enumerate()
            .map(|(i, id)| (id.clone(), i))
            .collect();
        self.idf = None;
        true
    }

    /// Recompute IDF with epsilon smoothing for negative values.
    fn recompute_idf(&mut self) {
        let n = self.doc_ids.len();
        if n == 0 {
            self.idf = Some(HashMap::new());
            return;
        }
        let mut raw: HashMap<String, f64> = HashMap::with_capacity(self.df.len());
        let mut neg_terms: Vec<String> = Vec::new();
        let mut idf_sum = 0.0;
        for (term, &df_t) in &self.df {
            let val = (((n as f64) - (df_t as f64) + 0.5) / ((df_t as f64) + 0.5)).ln();
            raw.insert(term.clone(), val);
            idf_sum += val;
            if val < 0.0 {
                neg_terms.push(term.clone());
            }
        }
        let avg_idf = if raw.is_empty() {
            0.0
        } else {
            idf_sum / (raw.len() as f64)
        };
        let floor = self.epsilon * avg_idf;
        for term in neg_terms {
            raw.insert(term, floor);
        }
        self.idf = Some(raw);
    }

    /// Top-k by descending score, > 0 only.
    fn search_internal(&mut self, tokens: &[String], top_k: usize) -> Vec<(String, f64)> {
        if self.idf.is_none() {
            self.recompute_idf();
        }
        let idf = self.idf.as_ref().expect("idf set above");
        let n = self.doc_ids.len();
        let avgdl = (self.total_tokens as f64) / (n as f64);
        let k1 = self.k1;
        let b = self.b;

        let mut scores = vec![0.0_f64; n];
        for qt in tokens {
            let qidf = match idf.get(qt) {
                Some(v) if *v != 0.0 => *v,
                _ => continue,
            };
            for i in 0..n {
                let tf = match self.doc_tf[i].get(qt) {
                    Some(&v) if v > 0 => v as f64,
                    _ => continue,
                };
                let dl = self.doc_lengths[i] as f64;
                let denom = if avgdl > 0.0 {
                    tf + k1 * (1.0 - b + b * dl / avgdl)
                } else {
                    tf + k1
                };
                scores[i] += qidf * (tf * (k1 + 1.0)) / denom;
            }
        }

        let mut ranked: Vec<(usize, f64)> = scores
            .into_iter()
            .enumerate()
            .filter(|(_, s)| *s > 0.0)
            .collect();
        ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        ranked.truncate(top_k);
        ranked
            .into_iter()
            .map(|(i, sc)| (self.doc_ids[i].clone(), sc))
            .collect()
    }

    fn save_now(&self) -> PyResult<()> {
        let state = PersistedState {
            doc_ids: self.doc_ids.clone(),
            corpus_texts: self.corpus_texts.clone(),
        };
        let payload = serde_json::to_string(&state)
            .map_err(|e| PyIOError::new_err(format!("serialize bm25 index: {e}")))?;
        if let Some(parent) = self.persist_path.parent() {
            fs::create_dir_all(parent)
                .map_err(|e| PyIOError::new_err(format!("create bm25 dir: {e}")))?;
        }
        let mut tmp = self.persist_path.clone();
        let new_ext = match tmp.extension() {
            Some(ext) => {
                let mut s = ext.to_os_string();
                s.push(".tmp");
                s
            }
            None => std::ffi::OsString::from("tmp"),
        };
        tmp.set_extension(new_ext);
        fs::write(&tmp, payload)
            .map_err(|e| PyIOError::new_err(format!("write bm25 tmp: {e}")))?;
        fs::rename(&tmp, &self.persist_path)
            .map_err(|e| PyIOError::new_err(format!("rename bm25 index: {e}")))?;
        Ok(())
    }

    fn mark_dirty(&mut self, py: Python<'_>) -> PyResult<()> {
        self.dirty = true;
        if eager_flush_env() {
            py.allow_threads(|| self.save_now())?;
            self.dirty = false;
            return Ok(());
        }
        if !self.atexit_registered {
            self.atexit_registered = true;
        }
        Ok(())
    }
}

fn eager_flush_env() -> bool {
    matches!(
        std::env::var("LOCALLENS_BM25_EAGER_FLUSH")
            .unwrap_or_default()
            .to_ascii_lowercase()
            .as_str(),
        "1" | "true" | "yes" | "on"
    )
}

/// Convert a list of Python dicts (`{"id": str, "chunk_text": str}`) into
/// owned `(String, String)` pairs so we can release the GIL before the
/// compute-heavy loop.
fn parse_documents(documents: &[Bound<'_, PyDict>]) -> PyResult<Vec<(String, String)>> {
    documents
        .iter()
        .map(|d| {
            let id_obj = d
                .get_item("id")?
                .ok_or_else(|| PyValueError::new_err("document missing 'id'"))?;
            let id: String = id_obj.extract()?;
            let text: String = match d.get_item("chunk_text")? {
                Some(obj) if !obj.is_none() => obj.extract()?,
                _ => String::new(),
            };
            Ok((id, text))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokenize_matches_python() {
        assert_eq!(
            tokenize("Hello, World! 42 foo_bar"),
            vec!["hello", "world", "42", "foo_bar"]
        );
    }

    #[test]
    fn tokenize_empty() {
        assert!(tokenize("").is_empty());
        assert!(tokenize("   ").is_empty());
    }

    #[test]
    fn add_then_remove_restores_empty_df() {
        let mut idx = BM25Index {
            persist_path: PathBuf::from("/tmp/nonexistent_test.json"),
            k1: 1.5,
            b: 0.75,
            epsilon: 0.25,
            doc_ids: Vec::new(),
            id_to_idx: HashMap::new(),
            doc_tf: Vec::new(),
            doc_lengths: Vec::new(),
            corpus_texts: Vec::new(),
            df: HashMap::new(),
            total_tokens: 0,
            idf: None,
            dirty: false,
            atexit_registered: false,
        };
        idx.add_internal("a".into(), "foo bar".into());
        idx.add_internal("b".into(), "bar baz".into());
        assert_eq!(idx.df.get("bar"), Some(&2));

        idx.remove_internal(vec!["a".into(), "b".into()]);
        assert!(idx.df.is_empty());
        assert!(idx.doc_ids.is_empty());
        assert_eq!(idx.total_tokens, 0);
    }

    #[test]
    fn update_existing_doc_id_rewrites_df() {
        let mut idx = BM25Index {
            persist_path: PathBuf::from("/tmp/nonexistent_test2.json"),
            k1: 1.5,
            b: 0.75,
            epsilon: 0.25,
            doc_ids: Vec::new(),
            id_to_idx: HashMap::new(),
            doc_tf: Vec::new(),
            doc_lengths: Vec::new(),
            corpus_texts: Vec::new(),
            df: HashMap::new(),
            total_tokens: 0,
            idf: None,
            dirty: false,
            atexit_registered: false,
        };
        idx.add_internal("foo".into(), "alpha beta".into());
        idx.add_internal("foo".into(), "gamma delta".into());
        assert!(idx.df.contains_key("gamma"));
        assert!(idx.df.contains_key("delta"));
        assert!(!idx.df.contains_key("alpha"));
        assert!(!idx.df.contains_key("beta"));
        assert_eq!(idx.doc_ids.len(), 1);
    }

    #[test]
    fn search_returns_ranked_results() {
        let mut idx = BM25Index {
            persist_path: PathBuf::from("/tmp/nonexistent_test3.json"),
            k1: 1.5,
            b: 0.75,
            epsilon: 0.25,
            doc_ids: Vec::new(),
            id_to_idx: HashMap::new(),
            doc_tf: Vec::new(),
            doc_lengths: Vec::new(),
            corpus_texts: Vec::new(),
            df: HashMap::new(),
            total_tokens: 0,
            idf: None,
            dirty: false,
            atexit_registered: false,
        };
        idx.add_internal("d1".into(), "the quick brown fox jumps over the lazy dog".into());
        idx.add_internal("d2".into(), "the lazy dog sleeps all day long in the sun".into());
        idx.add_internal("d3".into(), "quick quick quick fox fox jumps high".into());
        idx.add_internal("d4".into(), "the sun is shining brightly today".into());
        idx.add_internal("d5".into(), "a brown cat sits on the mat".into());

        let results = idx.search_internal(&tokenize("quick fox"), 10);
        assert!(!results.is_empty(), "search should return results");
        // d3 has more occurrences of query terms, should rank first or second
        assert!(results.iter().any(|(id, _)| id == "d3"), "d3 should be in results");
    }

    #[test]
    fn doc_count_tracks_size() {
        let mut idx = BM25Index {
            persist_path: PathBuf::from("/tmp/nonexistent_test4.json"),
            k1: 1.5,
            b: 0.75,
            epsilon: 0.25,
            doc_ids: Vec::new(),
            id_to_idx: HashMap::new(),
            doc_tf: Vec::new(),
            doc_lengths: Vec::new(),
            corpus_texts: Vec::new(),
            df: HashMap::new(),
            total_tokens: 0,
            idf: None,
            dirty: false,
            atexit_registered: false,
        };
        assert_eq!(idx.doc_ids.len(), 0);
        idx.add_internal("a".into(), "hello world".into());
        assert_eq!(idx.doc_ids.len(), 1);
        idx.add_internal("b".into(), "foo bar".into());
        assert_eq!(idx.doc_ids.len(), 2);
        idx.remove_internal(vec!["a".into()]);
        assert_eq!(idx.doc_ids.len(), 1);
    }

    #[test]
    fn bincode_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let bin_path = dir.path().join("test.bm25bin");
        let json_path = dir.path().join("test.json");

        let mut idx = BM25Index {
            persist_path: json_path,
            k1: 1.5,
            b: 0.75,
            epsilon: 0.25,
            doc_ids: Vec::new(),
            id_to_idx: HashMap::new(),
            doc_tf: Vec::new(),
            doc_lengths: Vec::new(),
            corpus_texts: Vec::new(),
            df: HashMap::new(),
            total_tokens: 0,
            idf: None,
            dirty: false,
            atexit_registered: false,
        };
        idx.add_internal("a".into(), "hello world foo".into());
        idx.add_internal("b".into(), "bar baz quux".into());

        // Save via bincode
        let state = BincodeState {
            doc_ids: idx.doc_ids.clone(),
            corpus_texts: idx.corpus_texts.clone(),
            doc_tf: idx.doc_tf.clone(),
            doc_lengths: idx.doc_lengths.clone(),
            df: idx.df.clone(),
            total_tokens: idx.total_tokens,
        };
        let encoded = bincode::serialize(&state).unwrap();
        fs::write(&bin_path, &encoded).unwrap();

        // Load back
        let raw = fs::read(&bin_path).unwrap();
        let loaded: BincodeState = bincode::deserialize(&raw).unwrap();
        assert_eq!(loaded.doc_ids, idx.doc_ids);
        assert_eq!(loaded.corpus_texts, idx.corpus_texts);
        assert_eq!(loaded.total_tokens, idx.total_tokens);
    }
}
