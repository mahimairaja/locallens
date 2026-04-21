mod languages;

use locallens_core::ChunkResult;
use pyo3::prelude::*;
use rayon::prelude::*;
use regex::Regex;
use unicode_segmentation::UnicodeSegmentation;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Split `text` on word boundaries using unicode segmentation and assemble
/// chunks that stay within `max_size` bytes, applying `overlap` bytes of
/// trailing context between consecutive chunks.  Chunks shorter than
/// `min_size` are discarded unless the result would otherwise be empty.
fn split_by_words(
    text: &str,
    base_offset: usize,
    max_size: usize,
    min_size: usize,
    overlap: usize,
) -> Vec<ChunkResult> {
    let words: Vec<&str> = text.unicode_words().collect();
    if words.is_empty() {
        if !text.is_empty() {
            return vec![ChunkResult {
                text: text.to_string(),
                start_offset: base_offset,
                end_offset: base_offset + text.len(),
            }];
        }
        return Vec::new();
    }

    let mut chunks: Vec<ChunkResult> = Vec::new();
    let mut buf = String::new();
    let mut chunk_start = base_offset;

    for word in &words {
        let needed = if buf.is_empty() {
            word.len()
        } else {
            1 + word.len() // space + word
        };

        if !buf.is_empty() && buf.len() + needed > max_size {
            // Emit current buffer
            chunks.push(ChunkResult {
                text: buf.clone(),
                start_offset: chunk_start,
                end_offset: chunk_start + buf.len(),
            });

            // Overlap: grab tail of current buffer
            let overlap_text = tail_overlap(&buf, overlap).to_string();
            chunk_start = chunk_start + buf.len() - overlap_text.len();
            buf.clear();
            if !overlap_text.is_empty() {
                buf.push_str(&overlap_text);
            }
        }

        if !buf.is_empty() {
            buf.push(' ');
        }
        buf.push_str(word);
    }

    if !buf.is_empty() {
        chunks.push(ChunkResult {
            text: buf.clone(),
            start_offset: chunk_start,
            end_offset: chunk_start + buf.len(),
        });
    }

    // Filter out too-small chunks unless that would leave nothing
    let filtered: Vec<ChunkResult> = chunks
        .iter()
        .filter(|c| c.text.len() >= min_size)
        .cloned()
        .collect();
    if filtered.is_empty() {
        chunks
    } else {
        filtered
    }
}

/// Return up to `n` bytes from the tail of `s`, breaking at a word boundary.
fn tail_overlap(s: &str, n: usize) -> &str {
    if n == 0 || s.is_empty() {
        return "";
    }
    if s.len() <= n {
        return s;
    }
    // Snap to a valid char boundary
    let raw_start = s.len() - n;
    let safe_start = s.ceil_char_boundary(raw_start);
    // Walk forward to the next space for a clean word boundary
    let start = match s[safe_start..].find(' ') {
        Some(pos) => safe_start + pos + 1,
        None => s.len(),
    };
    if start >= s.len() {
        ""
    } else {
        &s[start..]
    }
}

/// Core recursive splitter.  `separators` is a slice of regexes ordered from
/// coarsest to finest.  Each level tries to split on its regex, then recurses
/// into any section that is still too large.
fn split_recursively_inner(
    text: &str,
    base_offset: usize,
    separators: &[Regex],
    max_size: usize,
    min_size: usize,
    overlap: usize,
) -> Vec<ChunkResult> {
    // Base case: text fits
    if text.len() <= max_size {
        return vec![ChunkResult {
            text: text.to_string(),
            start_offset: base_offset,
            end_offset: base_offset + text.len(),
        }];
    }

    // No separators left: fall back to word-boundary splitting
    if separators.is_empty() {
        return split_by_words(text, base_offset, max_size, min_size, overlap);
    }

    let sep = &separators[0];
    let rest = &separators[1..];

    // Find all match start positions and split there
    let mut split_points: Vec<usize> = Vec::new();
    for m in sep.find_iter(text) {
        if m.start() > 0 {
            split_points.push(m.start());
        }
    }

    // If no splits found at this level, recurse with next separator
    if split_points.is_empty() {
        return split_recursively_inner(text, base_offset, rest, max_size, min_size, overlap);
    }

    // Build sections from split points
    let mut sections: Vec<(usize, &str)> = Vec::new();
    let mut prev = 0;
    for &sp in &split_points {
        if sp > prev {
            sections.push((prev, &text[prev..sp]));
        }
        prev = sp;
    }
    if prev < text.len() {
        sections.push((prev, &text[prev..]));
    }

    let mut chunks: Vec<ChunkResult> = Vec::new();
    let mut accumulated = String::new();
    let mut acc_offset = base_offset;

    for (sec_rel_offset, section) in sections {
        let would_be = if accumulated.is_empty() {
            section.len()
        } else {
            accumulated.len() + section.len()
        };

        if would_be <= max_size {
            if accumulated.is_empty() {
                acc_offset = base_offset + sec_rel_offset;
            }
            accumulated.push_str(section);
        } else {
            // Flush accumulated
            if !accumulated.is_empty() {
                if accumulated.len() > max_size {
                    chunks.extend(split_recursively_inner(
                        &accumulated,
                        acc_offset,
                        rest,
                        max_size,
                        min_size,
                        overlap,
                    ));
                } else {
                    chunks.push(ChunkResult {
                        text: accumulated.clone(),
                        start_offset: acc_offset,
                        end_offset: acc_offset + accumulated.len(),
                    });
                }
                accumulated.clear();
            }

            // Start new accumulation
            acc_offset = base_offset + sec_rel_offset;
            if section.len() > max_size {
                chunks.extend(split_recursively_inner(
                    section,
                    acc_offset,
                    rest,
                    max_size,
                    min_size,
                    overlap,
                ));
            } else {
                accumulated.push_str(section);
            }
        }
    }

    // Flush remaining
    if !accumulated.is_empty() {
        if accumulated.len() > max_size {
            chunks.extend(split_recursively_inner(
                &accumulated,
                acc_offset,
                rest,
                max_size,
                min_size,
                overlap,
            ));
        } else {
            chunks.push(ChunkResult {
                text: accumulated.clone(),
                start_offset: acc_offset,
                end_offset: acc_offset + accumulated.len(),
            });
        }
    }

    chunks
}

/// Apply overlap between adjacent chunks by prepending trailing context from
/// the previous chunk to the current one.
fn apply_overlap(chunks: &mut Vec<ChunkResult>, full_text: &str, overlap: usize) {
    if overlap == 0 || chunks.len() < 2 {
        return;
    }
    for i in 1..chunks.len() {
        let prev_end = chunks[i - 1].end_offset;
        let cur_start = chunks[i].start_offset;
        // Only skip if chunks already overlap or start at origin
        if cur_start < prev_end || cur_start == 0 {
            continue;
        }
        let overlap_start = if cur_start >= overlap {
            cur_start - overlap
        } else {
            0
        };
        // Walk forward to nearest space to avoid mid-word
        let actual_start = match full_text[overlap_start..cur_start].find(' ') {
            Some(pos) => overlap_start + pos + 1,
            None => cur_start, // no good break, skip overlap
        };
        if actual_start < cur_start && actual_start < full_text.len() {
            let overlap_str = &full_text[actual_start..cur_start];
            let mut new_text = String::with_capacity(overlap_str.len() + chunks[i].text.len());
            new_text.push_str(overlap_str);
            new_text.push_str(&chunks[i].text);
            chunks[i].text = new_text;
            chunks[i].start_offset = actual_start;
        }
    }
}

// ---------------------------------------------------------------------------
// Public API (Rust-level)
// ---------------------------------------------------------------------------

/// Split text recursively using the given separator regexes.
pub fn split_recursively(
    text: &str,
    separators: &[Regex],
    max_size: usize,
    min_size: usize,
    overlap: usize,
) -> Vec<ChunkResult> {
    if text.is_empty() {
        return Vec::new();
    }

    let mut chunks = split_recursively_inner(text, 0, separators, max_size, min_size, overlap);

    // Apply overlap
    apply_overlap(&mut chunks, text, overlap);

    // Discard chunks below min_size unless they are the only chunk
    let filtered: Vec<ChunkResult> = chunks
        .iter()
        .filter(|c| c.text.len() >= min_size)
        .cloned()
        .collect();
    if filtered.is_empty() {
        chunks
    } else {
        filtered
    }
}

// ---------------------------------------------------------------------------
// Python-exposed functions
// ---------------------------------------------------------------------------

/// Chunk plain text using word-boundary splitting with no language awareness.
#[pyfunction]
#[pyo3(signature = (text, max_size=1000, overlap=50, min_size=100))]
pub fn chunk_text(
    text: &str,
    max_size: usize,
    overlap: usize,
    min_size: usize,
) -> Vec<ChunkResult> {
    let default_seps: Vec<Regex> = vec![
        Regex::new(r"\n\n").unwrap(),
        Regex::new(r"\n").unwrap(),
        Regex::new(r"\. ").unwrap(),
    ];
    split_recursively(text, &default_seps, max_size, min_size, overlap)
}

/// Chunk text using language-aware separators selected by file type / extension.
#[pyfunction]
#[pyo3(signature = (text, file_type, max_size=1000, overlap=50, min_size=100))]
pub fn chunk_structured(
    text: &str,
    file_type: &str,
    max_size: usize,
    overlap: usize,
    min_size: usize,
) -> Vec<ChunkResult> {
    match languages::lookup(file_type) {
        Some(lang) => split_recursively(text, &lang.separators, max_size, min_size, overlap),
        None => chunk_text(text, max_size, overlap, min_size),
    }
}

/// Chunk a batch of (text, file_type) pairs in parallel.
#[pyfunction]
pub fn chunk_batch(
    documents: Vec<(String, String)>,
    max_size: usize,
    overlap: usize,
    min_size: usize,
) -> Vec<Vec<ChunkResult>> {
    documents
        .par_iter()
        .map(|(text, file_type)| chunk_structured(text, file_type, max_size, overlap, min_size))
        .collect()
}

/// Return metadata for all supported languages.
#[pyfunction]
pub fn supported_languages() -> Vec<std::collections::HashMap<String, Vec<String>>> {
    languages::all_languages()
        .iter()
        .map(|lang| {
            let mut map = std::collections::HashMap::new();
            map.insert("name".to_string(), vec![lang.name.to_string()]);
            map.insert(
                "aliases".to_string(),
                lang.aliases.iter().map(|a| a.to_string()).collect(),
            );
            map.insert(
                "extensions".to_string(),
                lang.extensions.iter().map(|e| e.to_string()).collect(),
            );
            map
        })
        .collect()
}

/// Register the chunker functions into a PyO3 module.
pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(chunk_text, m)?)?;
    m.add_function(wrap_pyfunction!(chunk_structured, m)?)?;
    m.add_function(wrap_pyfunction!(chunk_batch, m)?)?;
    m.add_function(wrap_pyfunction!(supported_languages, m)?)?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn plain_text(n: usize) -> String {
        let sentence = "The quick brown fox jumps over the lazy dog. ";
        sentence.repeat(n)
    }

    #[test]
    fn test_plain_text_within_bounds() {
        let text = plain_text(50);
        let chunks = chunk_text(&text, 200, 30, 50);
        for chunk in &chunks {
            assert!(
                chunk.text.len() <= 250, // max_size + overlap tolerance
                "chunk too large: {} bytes",
                chunk.text.len()
            );
        }
        assert!(!chunks.is_empty());
    }

    #[test]
    fn test_plain_text_covers_input() {
        let text = plain_text(10);
        let chunks = chunk_text(&text, 200, 0, 10);
        // Every character of the original text should appear in at least one chunk
        let mut covered = vec![false; text.len()];
        for chunk in &chunks {
            for i in chunk.start_offset..chunk.end_offset.min(text.len()) {
                covered[i] = true;
            }
        }
        let uncovered: usize = covered.iter().filter(|&&c| !c).count();
        // Allow some slack for whitespace trimming
        assert!(
            uncovered < 20,
            "too many uncovered bytes: {}",
            uncovered
        );
    }

    #[test]
    fn test_markdown_splits_on_headings() {
        let md = "# Introduction\n\nSome intro text that is long enough to be kept.\n\n## Methods\n\nDescription of methods that is also long enough.\n\n## Results\n\nResults go here and they are sufficiently long.";
        let chunks = chunk_structured(md, "markdown", 120, 0, 10);
        assert!(
            chunks.len() >= 2,
            "expected at least 2 chunks for markdown, got {}",
            chunks.len()
        );
        // First chunk should start with the heading
        assert!(
            chunks[0].text.starts_with("# "),
            "first chunk should start with heading: '{}'",
            &chunks[0].text[..40.min(chunks[0].text.len())]
        );
    }

    #[test]
    fn test_python_splits_on_def() {
        let py = "\
class Foo:
    def __init__(self):
        self.x = 1
        self.y = 2
        self.z = 3

    def bar(self):
        return self.x + self.y + self.z

    def baz(self):
        result = []
        for i in range(100):
            result.append(i * 2)
        return result

def standalone():
    print('hello world')
    print('another line')
    return 42
";
        let chunks = chunk_structured(py, "python", 120, 0, 10);
        assert!(
            chunks.len() >= 2,
            "expected at least 2 chunks for python, got {}",
            chunks.len()
        );
    }

    #[test]
    fn test_all_27_languages_produce_chunks() {
        // Sample input that works for any language: some lines with structure
        let sample = "line one here with content\nline two here with more\n\nblock two starts\nand continues\n\nanother block\nwith stuff\n";
        let sample_long = sample.repeat(5);

        let langs = languages::all_languages();
        assert!(
            langs.len() >= 27,
            "expected at least 27 languages, got {}",
            langs.len()
        );
        for lang in langs {
            let chunks = chunk_structured(&sample_long, lang.name, 200, 0, 10);
            assert!(
                !chunks.is_empty(),
                "language '{}' produced no chunks",
                lang.name
            );
        }
    }

    #[test]
    fn test_batch_equals_sequential() {
        let docs = vec![
            ("Hello world. This is a test document with enough text to chunk properly.".to_string(), "markdown".to_string()),
            ("fn main() {\n    println!(\"hello\");\n}\n\nfn other() {\n    let x = 1;\n}".to_string(), "rust".to_string()),
            ("def foo():\n    pass\n\ndef bar():\n    return 1\n".to_string(), "python".to_string()),
        ];

        let batch_result = chunk_batch(docs.clone(), 200, 10, 10);

        let sequential_result: Vec<Vec<ChunkResult>> = docs
            .iter()
            .map(|(text, ft)| chunk_structured(text, ft, 200, 10, 10))
            .collect();

        assert_eq!(batch_result.len(), sequential_result.len());
        for (b, s) in batch_result.iter().zip(sequential_result.iter()) {
            assert_eq!(b.len(), s.len(), "chunk count mismatch");
            for (bc, sc) in b.iter().zip(s.iter()) {
                assert_eq!(bc.text, sc.text);
                assert_eq!(bc.start_offset, sc.start_offset);
                assert_eq!(bc.end_offset, sc.end_offset);
            }
        }
    }

    #[test]
    fn test_empty_input() {
        let chunks = chunk_text("", 100, 10, 10);
        assert!(chunks.is_empty());
    }

    #[test]
    fn test_small_input_kept() {
        let chunks = chunk_text("tiny", 100, 10, 10);
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].text, "tiny");
    }

    #[test]
    fn test_unknown_language_falls_back() {
        let text = plain_text(10);
        let chunks = chunk_structured(&text, "unknown_lang", 200, 10, 10);
        assert!(!chunks.is_empty());
    }
}
