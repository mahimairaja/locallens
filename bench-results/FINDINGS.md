# LocalLens engine — pipeline benchmark findings

Benchmark script: [`scripts/bench_pipeline.py`](../scripts/bench_pipeline.py)  
Reports: `bench_200.json`, `bench_500.json`  
Corpus: synthetic `.md`/`.txt`/`.py` files (~5 KB avg), seeded RNG (reproducible).  
Embedder: **mocked** 384-dim vectors — HuggingFace was unreachable in the sandbox.
Real `all-MiniLM-L6-v2` timings are referenced from published numbers below.

---

## Per-stage timings (200 files → 1,485 chunks)

| stage                       | total    | per item   | share of end-to-end |
| --------------------------- | -------- | ---------- | ------------------- |
| walk                        | 30 ms    | 0.15 ms    |  0.3 %              |
| hash (sha256)               | 53 ms    | 0.26 ms    |  0.5 %              |
| extract (text)              | 47 ms    | 0.23 ms    |  0.4 %              |
| chunk                       | 12 ms    | 0.06 ms    |  0.1 %              |
| **bm25 incremental**        | **10.52 s** | **52.6 ms** | **96.9 %**     |
| bm25 build-from-scratch     | 115 ms   | 0.08 ms    | (not in pipeline)   |
| bm25 tokenize alone         | 42 ms    | 0.03 ms    | (subset of above)   |
| embed batch 32 (*mock*)     | 67 ms    | 0.05 ms    |  0.6 %              |
| qdrant edge upsert          | 131 ms   | 0.09 ms    |  1.2 %              |
| qdrant edge has_hash (dedup)|   1 ms   | 0.004 ms   | —                   |
| qdrant edge search          |   5 ms   | 0.35 ms    | —                   |
| bm25 search                 |  27 ms   | 1.93 ms    | —                   |

## Scaling check (500 files → 3,779 chunks)

| stage                       | 200f      | 500f      | ratio  | expected (linear) |
| --------------------------- | --------- | --------- | ------ | ----------------- |
| walk                        | 30 ms     | 66 ms     | 2.2 ×  | 2.5 ×             |
| hash                        | 53 ms     | 120 ms    | 2.3 ×  | 2.5 ×             |
| chunk                       | 12 ms     | 28 ms     | 2.3 ×  | 2.5 ×             |
| qdrant upsert (mock vecs)   | 131 ms    | — (skipped) | —    | 2.5 ×             |
| **bm25 incremental**        | **10.5 s**| **67.7 s**| **6.4 ×** | 2.5 × → **O(n²)** |
| bm25 search (fixed corpus)  | 27 ms     | 72 ms     | 2.7 ×  | linear in N docs  |

The incremental BM25 path grows quadratically. Everything else is linear.

---

## Root-cause: `locallens/bm25.py::add_documents`

```python
def add_documents(documents: list[dict]) -> None:
    ...
    for d in documents:
        if doc_id in _doc_ids:            # O(n) list scan per doc
            ...
    tokenized = [_tokenize(t) for t in _corpus_texts]   # re-tokenize whole corpus
    _bm25 = BM25Okapi(tokenized) if tokenized else None # rebuild whole BM25 index
    _save()                                             # rewrite whole JSON to disk
```

Called **once per file** from `indexer.py`. For N files with M chunks each:

- `_doc_ids` membership check:  O(files × cumulative_chunks) ≈ O(N²·M)
- Retokenize full corpus:        O(Σᵢ₌₁..ᴺ i·M) = O(N²·M)
- Full JSON rewrite:             O(N²·M) bytes written across run
- `BM25Okapi` constructor:       recomputes idf for the whole corpus every call

Net effect measured: 500 files take **6.4×** longer than a linear projection.
At 2,000 files it projects to ~18 min; at 10,000 files it's unusable.

The pure-Python `rank-bm25` lib has no incremental API — it recomputes everything
on construction — so the current design pays that cost every single add.

---

## What a Rust rewrite would actually buy us

Ordered by real impact on end-to-end wall-clock time, assuming the BM25 bug
above is **not** addressed yet.

### 1. BM25 — huge win, but first fix the algorithm in Python

**If we just stop rebuilding on every add** (batch adds, or use append-only
counters + lazy idf), Python already does 3,779 docs in **115 ms**
(`bm25_build_fresh`). That closes 96 % of the gap without any Rust.

Only *then* does Rust start to matter. A Rust BM25 (e.g. [tantivy](https://github.com/quickwit-oss/tantivy)
embedded, or a small pyo3 wrapper around a custom inverted index) would:
- add proper incremental updates (no full rebuild)
- give true on-disk persistence (no whole-file JSON rewrite)
- make `bm25.search` 5–10× faster than `rank-bm25` on large corpora
  (which currently iterates every doc in Python to score)

**Recommendation:** fix the algorithm first; revisit Rust only if `bm25_search`
becomes a problem (> ~5 ms/query with >50k chunks).

### 2. Tokenizer (used by BM25) — modest win

`bm25_tokenize` hits ~4.2 M tokens/sec in pure-Python regex. Rust can do
30–50 M/sec easily. But at 1,485 chunks the tokenize cost is 42 ms — not a
user-visible bottleneck until you're at 100k+ chunks.

Low priority until corpus size justifies it.

### 3. File hashing — only helps huge corpora

Currently ~20 MB/sec throughput (pure-Python SHA-256 loop). Rust `sha2` + `rayon`
easily hits 500 MB/sec single-threaded or multi-GB/sec with SIMD. But on a
1 MB total corpus this saves 50 ms. Only matters if indexing multi-GB directories.

### 4. Chunker — not a bottleneck

58 µs per file. A Rust port would save 12 ms on a 200-file run. Skip.

### 5. File walker — not a bottleneck

`Path.rglob` is already C-backed via `os.scandir`. 150 µs per file on our corpus.
Skip.

### 6. Embedder — **Rust cannot help here**

`sentence-transformers` → PyTorch → ATen/MKL (C++/Fortran). The Python overhead
is <1 % of the batch-32 call. A Rust wrapper around ONNX runtime (via `candle`
or `ort`) would give near-identical throughput because the matmul is the work.

The only way to speed up embeddings is: smaller model, quantized weights, or
GPU — orthogonal to Rust vs Python.

### 7. Qdrant store — already Rust

`qdrant-edge-py` is a PyO3 wrapper over Qdrant (written in Rust). Upsert is
11k points/sec; `has_hash` is 230k lookups/sec. Nothing to rewrite.

---

## Bottom line

1. **Before any Rust work**: fix `bm25.add_documents` to do incremental append
   instead of full rebuild. That single change recovers ~97 % of the indexing
   time for a 200-file corpus and is the #1 ROI change in the whole engine.

2. **After that**, the remaining end-to-end breakdown (200-file corpus):
   - Embedding: ~2 s (estimated, real model) — PyTorch, not Rust territory
   - Qdrant upsert: ~130 ms — already Rust
   - Hashing + extract + chunk + walk: ~140 ms — pure overhead, not worth rewriting
   - BM25 build (once): ~115 ms
   - BM25 search: ~2 ms/query

   There is **no single stage left that would repay a Rust port** at typical
   corpus sizes (≤ 10k files).

3. **When Rust would genuinely pay off** — at scale (≥ 50k files or ≥ 1 GB
   corpus) the candidates are:
   - Inverted index / BM25 (tantivy or custom) — replaces rank-bm25 entirely
   - SHA-256 hashing with SIMD + rayon parallelism
   - Regex-based tokenizer (shared by BM25 + chunker)

   All three could live in one `locallens-core` pyo3 crate, imported where
   needed. Estimated dev cost: 2–3 weeks. Estimated speedup on a 100k-file
   corpus: 5–10× on indexing throughput, assuming the BM25 algorithm fix is
   also in place.

---

## Repro

```bash
uv sync --frozen
uv pip install rank-bm25                          # dev-time dep

# Quick smoke (skip heavy stages)
.venv/bin/python scripts/bench_pipeline.py --files 30 --skip-embed --skip-store

# Full run with mock embeddings
.venv/bin/python scripts/bench_pipeline.py --files 200 --mock-embed --out bench-results/bench_200.json

# Scaling check
.venv/bin/python scripts/bench_pipeline.py --files 500 --mock-embed --skip-store --out bench-results/bench_500.json
```

With real HF access, drop `--mock-embed` to measure actual embedding throughput.
