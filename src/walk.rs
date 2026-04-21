//! Rust file walker + parallel SHA-256.
//!
//! Mirrors the inline walker/hasher previously duplicated across
//! `locallens/indexer.py`, `backend/app/services/indexer.py`, and
//! `backend/app/services/watcher.py`. The shared Python entry point
//! `locallens._file_core.walk_and_hash` delegates here when
//! `HAS_RUST_WALKER` is True; otherwise it falls back to the pure-Python
//! implementation.
//!
//! Hash output is byte-identical to `hashlib.sha256(path.read_bytes()).hexdigest()`
//! — the parity test in `tests/test_file_core.py` is the permanent guard.

use std::collections::HashSet;
use std::fs;
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};

use pyo3::exceptions::PyIOError;
use pyo3::prelude::*;
use rayon::prelude::*;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

#[pyclass(module = "locallens._locallens_rs")]
pub struct RustWalker {
    extensions: HashSet<String>,
    max_file_size_bytes: u64,
    skip_hidden: bool,
    follow_symlinks: bool,
    parallel: bool,
}

#[pymethods]
impl RustWalker {
    /// Construct a new walker.
    ///
    /// `extensions` must be lowercase and include the dot, e.g. `[".py", ".md"]`.
    #[new]
    #[pyo3(signature = (extensions, max_file_size_bytes, *, skip_hidden = true, follow_symlinks = true, parallel = true))]
    fn new(
        extensions: Vec<String>,
        max_file_size_bytes: u64,
        skip_hidden: bool,
        follow_symlinks: bool,
        parallel: bool,
    ) -> Self {
        Self {
            extensions: extensions.into_iter().map(|e| e.to_lowercase()).collect(),
            max_file_size_bytes,
            skip_hidden,
            follow_symlinks,
            parallel,
        }
    }

    /// Walk `root`, filter, and compute SHA-256 for each kept file.
    ///
    /// Returns `[(path_str, sha256_hex, size_bytes), ...]` sorted by path
    /// for byte-identical output with Python's `sorted(folder.rglob("*"))`.
    /// Unreadable files (permission denied, I/O error) are silently
    /// skipped — matches the Python walker's warn-and-continue behavior.
    fn walk_and_hash(
        &self,
        py: Python<'_>,
        root: PathBuf,
    ) -> PyResult<Vec<(String, String, u64)>> {
        if !root.exists() {
            return Ok(Vec::new());
        }
        let root_owned = root.clone();
        let extensions = self.extensions.clone();
        let max_bytes = self.max_file_size_bytes;
        let skip_hidden = self.skip_hidden;
        let follow_symlinks = self.follow_symlinks;
        let parallel = self.parallel;

        let out = py.allow_threads(move || {
            walk_and_hash_inner(
                &root_owned,
                &extensions,
                max_bytes,
                skip_hidden,
                follow_symlinks,
                parallel,
            )
        });
        Ok(out)
    }

    /// Single-file streaming SHA-256. Helper for the watcher path where
    /// we already know the file and just need the hash.
    #[staticmethod]
    fn hash_file(py: Python<'_>, path: PathBuf) -> PyResult<String> {
        let display = path.display().to_string();
        py.allow_threads(move || hash_one(&path))
            .map_err(|e| PyIOError::new_err(format!("hash {display}: {e}")))
    }
}

// ----- pure-Rust helpers (no pyo3 types on the signatures) -----

fn is_hidden_relative(path: &Path, root: &Path) -> bool {
    path.strip_prefix(root)
        .ok()
        .map(|rel| {
            rel.components()
                .any(|c| c.as_os_str().to_string_lossy().starts_with('.'))
        })
        .unwrap_or(false)
}

fn extension_matches(path: &Path, extensions: &HashSet<String>) -> bool {
    let Some(ext) = path.extension().and_then(|e| e.to_str()) else {
        return false;
    };
    let with_dot = format!(".{}", ext.to_lowercase());
    extensions.contains(&with_dot)
}

fn collect_candidates(
    root: &Path,
    extensions: &HashSet<String>,
    max_bytes: u64,
    skip_hidden: bool,
    follow_symlinks: bool,
) -> Vec<(PathBuf, u64)> {
    let mut out: Vec<(PathBuf, u64)> = Vec::new();
    let walker = WalkDir::new(root).follow_links(follow_symlinks);
    for entry in walker.into_iter().filter_map(|e| e.ok()) {
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        if skip_hidden && is_hidden_relative(path, root) {
            continue;
        }
        if !extension_matches(path, extensions) {
            continue;
        }
        let size = match entry.metadata() {
            Ok(md) => md.len(),
            Err(_) => continue,
        };
        if size > max_bytes {
            continue;
        }
        out.push((path.to_path_buf(), size));
    }
    out.sort_by(|a, b| a.0.cmp(&b.0));
    out
}

fn hash_one(path: &Path) -> std::io::Result<String> {
    let f = fs::File::open(path)?;
    let mut reader = BufReader::with_capacity(8192, f);
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 8192];
    loop {
        let n = reader.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

fn walk_and_hash_inner(
    root: &Path,
    extensions: &HashSet<String>,
    max_bytes: u64,
    skip_hidden: bool,
    follow_symlinks: bool,
    parallel: bool,
) -> Vec<(String, String, u64)> {
    let candidates = collect_candidates(root, extensions, max_bytes, skip_hidden, follow_symlinks);
    if parallel {
        candidates
            .par_iter()
            .filter_map(|(path, size)| match hash_one(path) {
                Ok(h) => Some((path.to_string_lossy().into_owned(), h, *size)),
                Err(_) => None,
            })
            .collect()
    } else {
        candidates
            .iter()
            .filter_map(|(path, size)| match hash_one(path) {
                Ok(h) => Some((path.to_string_lossy().into_owned(), h, *size)),
                Err(_) => None,
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    fn exts(v: &[&str]) -> HashSet<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn hex_hash_matches_empty_string() {
        // sha256("") == e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
        let d = tempdir().unwrap();
        let p = d.path().join("empty.txt");
        fs::write(&p, b"").unwrap();
        assert_eq!(
            hash_one(&p).unwrap(),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn extension_filter_is_case_insensitive() {
        let set = exts(&[".py", ".md"]);
        assert!(extension_matches(Path::new("/x/a.py"), &set));
        assert!(extension_matches(Path::new("/x/a.PY"), &set));
        assert!(extension_matches(Path::new("/x/a.Md"), &set));
        assert!(!extension_matches(Path::new("/x/a.txt"), &set));
        assert!(!extension_matches(Path::new("/x/noext"), &set));
    }

    #[test]
    fn hidden_any_component_skipped() {
        let root = Path::new("/repo");
        assert!(is_hidden_relative(Path::new("/repo/.git/hooks"), root));
        assert!(is_hidden_relative(Path::new("/repo/src/.hidden/f.py"), root));
        assert!(!is_hidden_relative(Path::new("/repo/src/lib.rs"), root));
    }

    #[test]
    fn walker_filters_and_hashes() {
        let d = tempdir().unwrap();
        fs::write(d.path().join("a.py"), b"hello").unwrap();
        fs::write(d.path().join("b.py"), b"world").unwrap();
        fs::write(d.path().join("c.txt"), b"skipme").unwrap();
        fs::create_dir(d.path().join(".hidden")).unwrap();
        fs::write(d.path().join(".hidden/x.py"), b"skipme").unwrap();

        let out = walk_and_hash_inner(
            d.path(),
            &exts(&[".py"]),
            10_000_000,
            true,  // skip_hidden
            true,  // follow_symlinks
            false, // parallel=false for deterministic test
        );
        assert_eq!(out.len(), 2);
        assert!(out[0].0.ends_with("a.py"));
        assert!(out[1].0.ends_with("b.py"));
        // sha256("hello") / sha256("world") — byte-compared as hex.
        assert_eq!(
            out[0].1,
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        );
        assert_eq!(
            out[1].1,
            "486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7"
        );
        assert_eq!(out[0].2, 5);
        assert_eq!(out[1].2, 5);
    }

    #[test]
    fn max_size_gate_skips_large() {
        let d = tempdir().unwrap();
        fs::write(d.path().join("big.py"), vec![b'x'; 2000]).unwrap();
        fs::write(d.path().join("small.py"), b"ok").unwrap();
        let out = walk_and_hash_inner(d.path(), &exts(&[".py"]), 1000, true, true, false);
        assert_eq!(out.len(), 1);
        assert!(out[0].0.ends_with("small.py"));
    }
}
