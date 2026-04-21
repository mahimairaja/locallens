# Performance

LocalLens includes optional Rust extensions that accelerate the performance-critical hot paths. The Rust code is compiled into the wheel by default via [maturin](https://www.maturin.rs/) and [PyO3](https://pyo3.rs/).

## Rust-accelerated modules

| Module | What it does | Speedup |
|---|---|---|
| **BM25** | Keyword search index build and query | 1.3x build, 3.2x search |
| **Chunker** | Structure-aware text chunking (markdown, code, paragraphs) | Parallel batch processing via rayon |
| **Walker** | File discovery + parallel SHA-256 hashing | 2-3x (parallel hashing) |
| **Watcher** | File system change detection | OS-native APIs (FSEvents, inotify) |

## Checking Rust status

Run `locallens doctor` to see whether the Rust extensions are active:

```
┌──────────────────────────────────────────────────────────────────────┐
│                          LocalLens Doctor                            │
├─────────────────┬────────┬───────────────────────────────────────────┤
│ Rust Extensions │   ✓    │ Active: BM25, Chunker, Walker, Watcher   │
└─────────────────┴────────┴───────────────────────────────────────────┘
```

If the row shows "Not available (pure-Python fallback)", the Rust extension was not compiled. This happens when installing from sdist without a Rust toolchain.

## Benchmark results

Measured on synthetic corpora with mock embeddings (`scripts/bench_pipeline.py`).

### BM25: algorithm fix + Rust (200 files, 1,485 chunks)

| Stage | Original | Python fix | Rust | vs Original |
|---|---|---|---|---|
| BM25 incremental | 10,520 ms | 54 ms | 42 ms | **250x** |
| BM25 search (14 queries) | 27 ms | 8 ms | 2.9 ms | **9x** |

### File walker (500 files)

| Stage | Python | Rust | Speedup |
|---|---|---|---|
| Walk + hash | 146 ms | 52 ms | **2.8x** |

### End-to-end indexing

| Scale | Time | Notes |
|---|---|---|
| 200 files | 0.27 s | Mock embeddings |
| 500 files | 0.44 s | Mock embeddings |
| 50k files | 69 s | Mock embeddings, all stages linear |

Real embedding time (sentence-transformers on CPU) adds 2-20 seconds depending on corpus size and hardware. The Rust modules accelerate everything around the embedding step.

## Running benchmarks yourself

```bash
# Quick smoke test
make bench

# Or directly
python scripts/bench_pipeline.py --files 200 --mock-embed

# Scaling check
python scripts/bench_pipeline.py --files 500 --mock-embed --skip-store

# Full run with real embeddings
python scripts/bench_pipeline.py --files 200
```

Results are saved as JSON with `--out report.json`. Detailed findings are in `bench-results/FINDINGS.md`.

## Fallback behavior

If the Rust extension is not available, LocalLens uses the pure-Python implementations transparently. Same API, same results, just slower on large corpora. The fallback is automatic and requires no configuration.

## Building from source

The Rust extension requires a Rust toolchain (1.70+):

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Build and install
pip install -e "."
# Or explicitly
maturin develop --release

# Verify
python -c "from locallens._rust import HAS_RUST; print(HAS_RUST)"
```

Pre-built wheels for Linux, macOS (x86_64 + ARM), and Windows are published to PyPI on each release.
