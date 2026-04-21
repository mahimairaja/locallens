//! File walker with .gitignore-aware traversal and parallel text extraction.
//!
//! Uses the `ignore` crate (respects .gitignore) as primary walker when a
//! `.git` directory exists at the root, falling back to `walkdir` otherwise.
//! Built-in skip list filters common noise directories regardless of walker.

use std::collections::HashSet;
use std::fs;
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use pyo3::prelude::*;
use rayon::prelude::*;
use sha2::{Digest, Sha256};

/// Directories and files always skipped during traversal.
const SKIP_LIST: &[&str] = &[
    "node_modules",
    ".venv",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".egg-info",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "target",
    ".DS_Store",
];

/// Text file extensions (UTF-8 with latin-1 fallback).
const TEXT_EXTENSIONS: &[&str] = &[
    "txt", "md", "rst", "csv", "tsv", "json", "toml", "yaml", "yml", "env", "cfg", "ini", "conf",
];

/// Code file extensions (UTF-8 only).
const CODE_EXTENSIONS: &[&str] = &[
    "py", "js", "ts", "jsx", "tsx", "go", "rs", "java", "c", "cpp", "h", "hpp", "rb", "swift",
    "kt", "scala", "cs", "php", "sql", "sh", "bash", "zsh", "fish",
];

/// Binary/complex file extensions (not readable as text).
const BINARY_EXTENSIONS: &[&str] = &[
    "pdf", "docx", "xlsx", "pptx", "epub", "eml", "msg",
];

// ---------------------------------------------------------------------------
// Public pyfunction API
// ---------------------------------------------------------------------------

/// Walk a folder and return all matching files as `FileEntry` objects.
///
/// When `extensions` is `None`, all files are returned (minus skip list).
/// When provided, only files whose extension (without dot, lowercased) is in
/// the list are included.
#[pyfunction]
#[pyo3(signature = (folder, max_file_size_mb=50, extensions=None))]
pub fn walk_files(
    py: Python<'_>,
    folder: &str,
    max_file_size_mb: u64,
    extensions: Option<Vec<String>>,
) -> PyResult<Vec<locallens_core::FileEntry>> {
    let root = PathBuf::from(folder);
    if !root.exists() {
        return Ok(Vec::new());
    }
    let max_bytes = max_file_size_mb * 1024 * 1024;
    let ext_filter: Option<HashSet<String>> = extensions.map(|v| {
        v.into_iter()
            .map(|e| e.to_lowercase().trim_start_matches('.').to_string())
            .collect()
    });

    let entries = py.allow_threads(move || collect_entries(&root, max_bytes, ext_filter.as_ref()));
    Ok(entries)
}

/// Read text/code files in parallel and return their contents.
///
/// Returns `Vec<(path, Option<text>)>`. Binary/complex files yield `None`.
/// Text files are read as UTF-8 with latin-1 fallback; code files as strict
/// UTF-8 (returning `None` on decode failure).
#[pyfunction]
pub fn extract_texts(
    py: Python<'_>,
    file_paths: Vec<String>,
) -> PyResult<Vec<(String, Option<String>)>> {
    let results = py.allow_threads(move || {
        file_paths
            .par_iter()
            .map(|p| {
                let text = read_file_text(Path::new(p));
                (p.clone(), text)
            })
            .collect::<Vec<_>>()
    });
    Ok(results)
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

fn should_skip(name: &str) -> bool {
    SKIP_LIST.iter().any(|s| *s == name)
}

fn ext_lower(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|e| e.to_lowercase())
}

fn extension_allowed(path: &Path, filter: Option<&HashSet<String>>) -> bool {
    match filter {
        None => true,
        Some(set) => match ext_lower(path) {
            Some(ext) => set.contains(&ext),
            None => false,
        },
    }
}

fn modified_at(path: &Path) -> f64 {
    fs::metadata(path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

/// Determine whether a `.git` directory exists at the root level.
fn has_git_dir(root: &Path) -> bool {
    root.join(".git").is_dir()
}

/// Collect file entries using the `ignore` crate (respects .gitignore) when
/// a `.git` directory is present, otherwise fall back to `walkdir`.
fn collect_entries(
    root: &Path,
    max_bytes: u64,
    ext_filter: Option<&HashSet<String>>,
) -> Vec<locallens_core::FileEntry> {
    let mut entries = Vec::new();

    if has_git_dir(root) {
        collect_with_ignore(root, max_bytes, ext_filter, &mut entries);
    } else {
        collect_with_walkdir(root, max_bytes, ext_filter, &mut entries);
    }

    entries.sort_by(|a, b| a.path.cmp(&b.path));
    entries
}

fn collect_with_ignore(
    root: &Path,
    max_bytes: u64,
    ext_filter: Option<&HashSet<String>>,
    out: &mut Vec<locallens_core::FileEntry>,
) {
    let walker = ignore::WalkBuilder::new(root)
        .hidden(false) // We handle skip list ourselves
        .git_ignore(true)
        .git_global(true)
        .git_exclude(true)
        .build();

    for entry in walker.into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
            if should_skip(name) {
                continue;
            }
        }
        // Check if any ancestor directory is in the skip list
        if path_has_skipped_component(path, root) {
            continue;
        }
        if !extension_allowed(path, ext_filter) {
            continue;
        }
        let size = match fs::metadata(path) {
            Ok(md) => md.len(),
            Err(_) => continue,
        };
        if size > max_bytes {
            continue;
        }
        let ext = ext_lower(path).unwrap_or_default();
        let file_name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        out.push(locallens_core::FileEntry {
            path: path.to_string_lossy().into_owned(),
            file_name,
            extension: ext,
            size_bytes: size,
            modified_at: modified_at(path),
        });
    }
}

fn collect_with_walkdir(
    root: &Path,
    max_bytes: u64,
    ext_filter: Option<&HashSet<String>>,
    out: &mut Vec<locallens_core::FileEntry>,
) {
    let walker = walkdir::WalkDir::new(root).same_file_system(true);

    for entry in walker.into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if !entry.file_type().is_file() {
            continue;
        }
        if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
            if should_skip(name) {
                continue;
            }
        }
        if path_has_skipped_component(path, root) {
            continue;
        }
        if !extension_allowed(path, ext_filter) {
            continue;
        }
        let size = match entry.metadata() {
            Ok(md) => md.len(),
            Err(_) => continue,
        };
        if size > max_bytes {
            continue;
        }
        let ext = ext_lower(path).unwrap_or_default();
        let file_name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();

        out.push(locallens_core::FileEntry {
            path: path.to_string_lossy().into_owned(),
            file_name,
            extension: ext,
            size_bytes: size,
            modified_at: modified_at(path),
        });
    }
}

/// Returns true if any path component between `root` and `path` is in the
/// skip list.
fn path_has_skipped_component(path: &Path, root: &Path) -> bool {
    if let Ok(rel) = path.strip_prefix(root) {
        for component in rel.components() {
            let name = component.as_os_str().to_string_lossy();
            if should_skip(&name) {
                return true;
            }
        }
    }
    false
}

/// Read a file as text if it is a known text or code file, return None for
/// binary/complex files or unknown extensions.
fn read_file_text(path: &Path) -> Option<String> {
    let ext = ext_lower(path)?;
    let ext_str = ext.as_str();

    if BINARY_EXTENSIONS.contains(&ext_str) {
        return None;
    }

    let is_text = TEXT_EXTENSIONS.contains(&ext_str);
    let is_code = CODE_EXTENSIONS.contains(&ext_str);

    if !is_text && !is_code {
        // Unknown extension: try reading as UTF-8, return None on failure
        return read_utf8(path);
    }

    if is_text {
        // UTF-8 with latin-1 fallback
        read_utf8_with_latin1_fallback(path)
    } else {
        // Code: strict UTF-8
        read_utf8(path)
    }
}

fn read_utf8(path: &Path) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    String::from_utf8(bytes).ok()
}

fn read_utf8_with_latin1_fallback(path: &Path) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    match String::from_utf8(bytes.clone()) {
        Ok(s) => Some(s),
        Err(_) => {
            // Latin-1: each byte maps to the same Unicode code point
            Some(bytes.iter().map(|&b| b as char).collect())
        }
    }
}

/// Streaming SHA-256 hash of a single file.
#[allow(dead_code)]
pub fn hash_one(path: &Path) -> std::io::Result<String> {
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    #[test]
    fn hex_hash_matches_empty_string() {
        let d = tempdir().unwrap();
        let p = d.path().join("empty.txt");
        fs::write(&p, b"").unwrap();
        assert_eq!(
            hash_one(&p).unwrap(),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
    }

    #[test]
    fn extension_filter_works() {
        let mut set = HashSet::new();
        set.insert("py".to_string());
        set.insert("md".to_string());

        assert!(extension_allowed(Path::new("/x/a.py"), Some(&set)));
        assert!(extension_allowed(Path::new("/x/a.PY"), Some(&set)));
        assert!(extension_allowed(Path::new("/x/a.Md"), Some(&set)));
        assert!(!extension_allowed(Path::new("/x/a.txt"), Some(&set)));
        assert!(!extension_allowed(Path::new("/x/noext"), Some(&set)));
        // None filter accepts everything
        assert!(extension_allowed(Path::new("/x/a.txt"), None));
    }

    #[test]
    fn skip_list_filters_directories() {
        let d = tempdir().unwrap();
        let root = d.path();

        // Create files inside skip-listed directories
        fs::create_dir_all(root.join("node_modules")).unwrap();
        fs::write(root.join("node_modules/index.js"), b"skip").unwrap();
        fs::create_dir_all(root.join("__pycache__")).unwrap();
        fs::write(root.join("__pycache__/mod.pyc"), b"skip").unwrap();
        fs::create_dir_all(root.join(".venv/lib")).unwrap();
        fs::write(root.join(".venv/lib/site.py"), b"skip").unwrap();
        fs::create_dir_all(root.join("target/debug")).unwrap();
        fs::write(root.join("target/debug/main.rs"), b"skip").unwrap();

        // Create a non-skipped file
        fs::write(root.join("main.py"), b"hello").unwrap();

        let entries = collect_entries(root, 100_000_000, None);
        assert_eq!(entries.len(), 1, "only main.py should survive: {:?}", entries);
        assert!(entries[0].path.ends_with("main.py"));
    }

    #[test]
    fn skip_list_file_level() {
        let d = tempdir().unwrap();
        let root = d.path();
        fs::write(root.join(".DS_Store"), b"skip").unwrap();
        fs::write(root.join("readme.md"), b"keep").unwrap();

        let entries = collect_entries(root, 100_000_000, None);
        assert_eq!(entries.len(), 1);
        assert!(entries[0].path.ends_with("readme.md"));
    }

    #[test]
    fn walker_with_extension_filter() {
        let d = tempdir().unwrap();
        let root = d.path();
        fs::write(root.join("a.py"), b"hello").unwrap();
        fs::write(root.join("b.py"), b"world").unwrap();
        fs::write(root.join("c.txt"), b"skip").unwrap();

        let mut exts = HashSet::new();
        exts.insert("py".to_string());

        let entries = collect_entries(root, 100_000_000, Some(&exts));
        assert_eq!(entries.len(), 2);
        assert!(entries[0].path.ends_with("a.py"));
        assert!(entries[1].path.ends_with("b.py"));
    }

    #[test]
    fn max_size_gate() {
        let d = tempdir().unwrap();
        let root = d.path();
        fs::write(root.join("big.py"), vec![b'x'; 2000]).unwrap();
        fs::write(root.join("small.py"), b"ok").unwrap();

        let entries = collect_entries(root, 1000, None);
        assert_eq!(entries.len(), 1);
        assert!(entries[0].path.ends_with("small.py"));
    }

    #[test]
    fn extract_texts_reads_text_files() {
        let d = tempdir().unwrap();
        let txt = d.path().join("hello.txt");
        let py = d.path().join("main.py");
        let pdf = d.path().join("doc.pdf");

        fs::write(&txt, "hello world").unwrap();
        fs::write(&py, "print('hi')").unwrap();
        fs::write(&pdf, b"\x25PDF-1.4").unwrap();

        let paths = vec![
            txt.to_string_lossy().into_owned(),
            py.to_string_lossy().into_owned(),
            pdf.to_string_lossy().into_owned(),
        ];

        let results: Vec<(String, Option<String>)> = paths
            .par_iter()
            .map(|p| {
                let text = read_file_text(Path::new(p));
                (p.clone(), text)
            })
            .collect();

        assert_eq!(results.len(), 3);
        // Text file
        assert!(results.iter().find(|(p, _)| p.ends_with("hello.txt")).unwrap().1.is_some());
        // Code file
        assert!(results.iter().find(|(p, _)| p.ends_with("main.py")).unwrap().1.is_some());
        // Binary file
        assert!(results.iter().find(|(p, _)| p.ends_with("doc.pdf")).unwrap().1.is_none());
    }

    #[test]
    fn extract_texts_latin1_fallback() {
        let d = tempdir().unwrap();
        let txt = d.path().join("latin.txt");
        // Write bytes that are valid latin-1 but not valid UTF-8
        fs::write(&txt, &[0xC0, 0xE9, 0xF1]).unwrap();

        let result = read_file_text(txt.as_path());
        assert!(result.is_some(), "latin-1 fallback should produce a string");
        // 3 latin-1 bytes become 3 chars (but 6 UTF-8 bytes)
        assert_eq!(result.as_ref().unwrap().chars().count(), 3);
    }

    #[test]
    fn walkdir_fallback_when_no_git() {
        let d = tempdir().unwrap();
        let root = d.path();
        // No .git directory
        fs::write(root.join("a.rs"), b"fn main() {}").unwrap();

        assert!(!has_git_dir(root));
        let entries = collect_entries(root, 100_000_000, None);
        assert_eq!(entries.len(), 1);
        assert!(entries[0].path.ends_with("a.rs"));
    }

    #[test]
    fn ignore_walker_used_with_git() {
        let d = tempdir().unwrap();
        let root = d.path();
        fs::create_dir(root.join(".git")).unwrap();
        fs::write(root.join("a.rs"), b"fn main() {}").unwrap();

        assert!(has_git_dir(root));
        let entries = collect_entries(root, 100_000_000, None);
        assert_eq!(entries.len(), 1);
        assert!(entries[0].path.ends_with("a.rs"));
    }
}
