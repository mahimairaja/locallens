//! Rust port of `locallens/chunker.py`.
//!
//! Structure-aware text chunking with word-boundary overlap. Produces
//! identical output to the Python implementation for the same inputs.
//!
//! Exposed to Python as module-level functions `chunk_text` and
//! `chunk_batch` (rayon-parallel batch variant).

use std::sync::OnceLock;

use pyo3::prelude::*;
use rayon::prelude::*;
use regex::Regex;

const MAX_CHUNK: usize = 1000;
const MIN_CHUNK: usize = 100;
const OVERLAP: usize = 50;

// ── static regex patterns ──────────────────────────────────────────

fn heading_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^#{1,6}\s+").unwrap())
}

fn code_boundary_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?m)^(?:def |class |function |fn |func |export function |export default function |async function )",
        )
        .unwrap()
    })
}

fn paragraph_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\n\s*\n").unwrap())
}

fn sheet_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)(?=^Sheet: )").unwrap())
}

// ── core helpers ───────────────────────────────────────────────────

/// Simple char-based subdivision with word-boundary respect.
/// Snap a byte index to the nearest valid UTF-8 char boundary,
/// searching backward. Returns 0 if no boundary found above 0.
fn snap_back(text: &str, idx: usize) -> usize {
    let mut i = idx.min(text.len());
    while i > 0 && !text.is_char_boundary(i) {
        i -= 1;
    }
    i
}

/// Snap a byte index forward to the next valid UTF-8 char boundary.
fn snap_forward(text: &str, idx: usize) -> usize {
    let mut i = idx.min(text.len());
    while i < text.len() && !text.is_char_boundary(i) {
        i += 1;
    }
    i
}

fn subdivide(text: &str, max_size: usize, overlap: usize) -> Vec<String> {
    let text = text.trim();
    if text.is_empty() {
        return vec![];
    }

    let text_len = text.len();
    let mut chunks = Vec::new();
    let mut start = 0;

    while start < text_len {
        let mut end = snap_back(text, (start + max_size).min(text_len));

        // Walk back to nearest space for word boundary
        if end < text_len {
            if let Some(pos) = text[start..end].rfind(' ') {
                if pos > 0 {
                    end = start + pos;
                }
            }
        }

        let chunk = text[start..end].trim();
        if chunk.len() >= MIN_CHUNK {
            chunks.push(chunk.to_string());
        }

        let advance = if end > overlap { end - overlap } else { end };
        start = snap_forward(text, start.max(advance).max(start + 1));
    }

    chunks
}

/// Split text at regex match positions, keeping each match with the
/// section that follows it. Mirrors Python `_split_by_pattern`.
fn split_by_pattern(text: &str, pattern: &Regex) -> Vec<String> {
    let positions: Vec<usize> = pattern.find_iter(text).map(|m| m.start()).collect();
    if positions.is_empty() {
        return vec![text.to_string()];
    }

    let mut sections = Vec::new();

    // Text before first match
    if positions[0] > 0 {
        let pre = text[..positions[0]].trim();
        if !pre.is_empty() {
            sections.push(pre.to_string());
        }
    }

    for (i, &pos) in positions.iter().enumerate() {
        let end = if i + 1 < positions.len() {
            positions[i + 1]
        } else {
            text.len()
        };
        let section = text[pos..end].trim();
        if !section.is_empty() {
            sections.push(section.to_string());
        }
    }

    sections
}

// ── mode-specific chunkers ─────────────────────────────────────────

fn chunk_markdown(text: &str, size: usize, overlap: usize) -> Vec<String> {
    let sections = split_by_pattern(text, heading_re());
    let mut chunks = Vec::new();
    for section in sections {
        if section.len() <= size {
            if section.len() >= MIN_CHUNK {
                chunks.push(section);
            }
        } else {
            chunks.extend(subdivide(&section, size, overlap));
        }
    }
    chunks
}

fn chunk_code(text: &str, size: usize, overlap: usize) -> Vec<String> {
    let sections = split_by_pattern(text, code_boundary_re());
    let mut chunks = Vec::new();
    for section in sections {
        if section.len() <= size {
            if section.len() >= MIN_CHUNK {
                chunks.push(section);
            }
        } else {
            chunks.extend(subdivide(&section, size, overlap));
        }
    }
    chunks
}

fn chunk_paragraphs(text: &str, size: usize, overlap: usize) -> Vec<String> {
    let paragraphs: Vec<&str> = paragraph_re().split(text).collect();
    let mut chunks: Vec<String> = Vec::new();
    let mut current = String::new();

    for para in paragraphs {
        let para = para.trim();
        if para.is_empty() {
            continue;
        }

        if current.is_empty() {
            current = para.to_string();
        } else if current.len() + para.len() + 2 <= size {
            current.push_str("\n\n");
            current.push_str(para);
        } else {
            if current.len() >= MIN_CHUNK {
                chunks.push(current.clone());
            } else if let Some(last) = chunks.last_mut() {
                last.push_str("\n\n");
                last.push_str(&current);
            }
            current = para.to_string();
        }
    }

    if !current.is_empty() {
        if current.len() >= MIN_CHUNK {
            chunks.push(current);
        } else if let Some(last) = chunks.last_mut() {
            last.push_str("\n\n");
            last.push_str(&current);
        }
    }

    // Subdivide oversized chunks
    let mut final_chunks = Vec::new();
    for chunk in chunks {
        if chunk.len() > size {
            final_chunks.extend(subdivide(&chunk, size, overlap));
        } else {
            final_chunks.push(chunk);
        }
    }

    final_chunks
}

fn chunk_spreadsheet(text: &str, size: usize, overlap: usize) -> Vec<String> {
    let blocks: Vec<&str> = sheet_re().split(text).collect();
    let mut chunks = Vec::new();

    for block in blocks {
        let block = block.trim();
        if block.is_empty() {
            continue;
        }
        if block.len() <= size {
            if block.len() >= MIN_CHUNK {
                chunks.push(block.to_string());
            }
        } else {
            // Split by row groups
            let lines: Vec<&str> = block.split('\n').collect();
            let mut current = String::new();
            for line in lines {
                if current.is_empty() {
                    current = line.to_string();
                } else if current.len() + line.len() + 1 <= size {
                    current.push('\n');
                    current.push_str(line);
                } else {
                    if current.len() >= MIN_CHUNK {
                        chunks.push(current.clone());
                    }
                    current = line.to_string();
                }
            }
            if !current.is_empty() && current.len() >= MIN_CHUNK {
                chunks.push(current);
            }
        }
    }

    // If sheet_re didn't match anything meaningful and we got nothing,
    // fall back to subdivide.
    if chunks.is_empty() && !text.trim().is_empty() {
        return subdivide(text, size, overlap);
    }

    chunks
}

// ── Python-exposed functions ───────────────────────────────────────

/// Structure-aware text chunking. Dispatches by `file_type` extension.
#[pyfunction]
#[pyo3(signature = (text, size=MAX_CHUNK, overlap=OVERLAP, file_type=""))]
pub fn chunk_text(text: &str, size: usize, overlap: usize, file_type: &str) -> Vec<String> {
    if text.trim().is_empty() {
        return vec![];
    }

    let ft = file_type.to_lowercase();
    match ft.as_str() {
        ".md" | ".txt" => chunk_markdown(text, size, overlap),
        ".py" | ".js" | ".ts" | ".go" | ".rs" | ".java" | ".c" | ".cpp" | ".rb" => {
            chunk_code(text, size, overlap)
        }
        ".pdf" | ".docx" | ".pptx" | ".html" => chunk_paragraphs(text, size, overlap),
        ".xlsx" | ".xls" | ".csv" | ".tsv" => chunk_spreadsheet(text, size, overlap),
        _ => subdivide(text, size, overlap),
    }
}

/// Parallel batch chunking via rayon.
///
/// Each item is ``(text, size, overlap, file_type)``.
#[pyfunction]
pub fn chunk_batch(items: Vec<(String, usize, usize, String)>) -> Vec<Vec<String>> {
    items
        .into_par_iter()
        .map(|(text, size, overlap, file_type)| chunk_text(&text, size, overlap, &file_type))
        .collect()
}

// ── tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn subdivide_respects_word_boundary() {
        let text = "hello world this is a test of word boundary splitting in the chunker";
        let chunks = subdivide(text, 30, 5);
        // Every chunk should end at a word boundary (no mid-word splits)
        for chunk in &chunks {
            assert!(!chunk.ends_with(|c: char| c.is_alphanumeric() && c != ' '));
        }
        assert!(!chunks.is_empty());
    }

    #[test]
    fn subdivide_drops_tiny_chunks() {
        let text = "short";
        let chunks = subdivide(text, 1000, 50);
        // "short" is < MIN_CHUNK (100), so should be dropped
        assert!(chunks.is_empty());
    }

    #[test]
    fn subdivide_keeps_long_enough_text() {
        let text = "a ".repeat(60); // 120 chars, above MIN_CHUNK
        let chunks = subdivide(&text, 1000, 50);
        assert_eq!(chunks.len(), 1);
    }

    #[test]
    fn chunk_markdown_splits_on_headings() {
        let text = format!(
            "# Title\n\n{}\n\n## Section 2\n\n{}",
            "Content one. ".repeat(20),
            "Content two. ".repeat(20)
        );
        let chunks = chunk_text(&text, 1000, 50, ".md");
        assert!(chunks.len() >= 2, "Expected at least 2 chunks, got {}", chunks.len());
    }

    #[test]
    fn chunk_code_splits_on_functions() {
        let text = format!(
            "def foo():\n    {}\n\ndef bar():\n    {}\n\nclass Baz:\n    {}",
            "pass # ".repeat(30),
            "pass # ".repeat(30),
            "pass # ".repeat(30),
        );
        let chunks = chunk_text(&text, 1000, 50, ".py");
        assert!(chunks.len() >= 2, "Expected at least 2 chunks, got {}", chunks.len());
    }

    #[test]
    fn chunk_text_dispatches_by_extension() {
        let long_text = "word ".repeat(300);

        let md_chunks = chunk_text(&long_text, 200, 20, ".md");
        let py_chunks = chunk_text(&long_text, 200, 20, ".py");
        let pdf_chunks = chunk_text(&long_text, 200, 20, ".pdf");
        let csv_chunks = chunk_text(&long_text, 200, 20, ".csv");
        let other_chunks = chunk_text(&long_text, 200, 20, ".xyz");

        // All should produce non-empty results
        assert!(!md_chunks.is_empty());
        assert!(!py_chunks.is_empty());
        assert!(!pdf_chunks.is_empty());
        assert!(!csv_chunks.is_empty());
        assert!(!other_chunks.is_empty());
    }

    #[test]
    fn empty_text_returns_empty() {
        assert!(chunk_text("", 1000, 50, ".md").is_empty());
        assert!(chunk_text("   ", 1000, 50, ".py").is_empty());
    }

    #[test]
    fn chunk_batch_parallel() {
        let items: Vec<(String, usize, usize, String)> = (0..10)
            .map(|i| {
                (
                    format!("document {} content. ", i).repeat(30),
                    200,
                    20,
                    ".txt".to_string(),
                )
            })
            .collect();
        let results = chunk_batch(items);
        assert_eq!(results.len(), 10);
        for r in &results {
            assert!(!r.is_empty());
        }
    }
}
