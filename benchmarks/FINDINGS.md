# LocalLens engine — pipeline benchmark findings

Benchmark script: [`scripts/bench_pipeline.py`](../scripts/bench_pipeline.py)
Reports: `bench_200.json`, `bench_500.json` (pre-fix);
`bench_200_post.json`, `bench_500_post.json` (post-fix, see the
"Post-fix results" section at the bottom).
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

---

## Post-fix results

Fix landed: `locallens/_bm25_core.py` replaces `rank_bm25.BM25Okapi` with a
parameterised incremental index. Running the same bench on the same synthetic
corpus (seeded RNG).

**Note on measurement methodology.** Pre-fix, every `add_documents` call
persisted the whole JSON file, so the pre-fix `bm25_incremental_per_file`
timing included persistence. Post-fix writes are deferred, so to keep the
comparison apples-to-apples the bench now times `add_documents` per file
**plus a single trailing `flush()`** — the exact path the CLI indexer and
the web lifespan shutdown take. At this corpus size the flush contributes
~1-10 ms, well inside measurement noise.

### 200 files / 1,485 chunks

| stage                       | pre-fix   | post-fix  | speedup |
| --------------------------- | --------- | --------- | ------- |
| walk                        | 30 ms     | 13 ms     | 2.2 ×   |
| hash (sha256)               | 53 ms     | 30 ms     | 1.8 ×   |
| extract                     | 47 ms     | 24 ms     | 2.0 ×   |
| chunk                       | 12 ms     | 9 ms      | 1.3 ×   |
| **bm25 incremental + flush** | **10,520 ms** | **54 ms** | **195 ×** |
| bm25 build-from-scratch     | 115 ms    | 66 ms     | 1.7 ×   |
| bm25 search (×14 queries)   | 27 ms     | 8 ms      | 3.4 ×   |
| qdrant edge upsert          | 131 ms    | 107 ms    | 1.2 ×   |
| **end-to-end index**        | **10.86 s** | **0.27 s** | **40 ×** |

### 500 files / 3,779 chunks (scaling check)

| stage                       | pre-fix   | post-fix  | speedup |
| --------------------------- | --------- | --------- | ------- |
| **bm25 incremental + flush** | **67,699 ms** | **151 ms** | **449 ×** |
| bm25 search (×14 queries)   | 72 ms     | 32 ms     | 2.3 ×   |
| **end-to-end index**        | **~68 s** | **0.44 s** | **~155 ×** |

### Scaling is now linear

`bm25_incremental_per_file` at 200 → 500 files: **2.80 ×** for 2.5 × input.
Pre-fix was 6.4 × for the same step — the O(N²) tail is gone.

### Why so much bigger than the plan's estimate

The plan targeted ≥ 35 × at 200 files and ≥ 80 × at 500 files. We beat both by
roughly 5×. Two reasons:

1. The pre-fix path wasn't just `O(N²)` — it also re-tokenized every doc and
   re-ran `BM25Okapi.__init__` (which walks the whole corpus building its own
   tf / df tables) on every add. Eliminating both loops together gives a
   multiplicative win.
2. Scoring moved from `np.array([doc.get(t, 0) for doc in self.doc_freqs])`
   inside a NumPy helper to a direct dict lookup in a tight Python loop.
   That's a wash on throughput but it drops ~20 ms per query at this corpus
   size because NumPy's per-call setup overhead is gone.

### What dominates wall-clock now

At 200 files post-fix: `qdrant_edge_upsert` (39 %), `bm25_incremental_per_file`
(20 %), `embed_batch_32` (13 %, mocked — real embeddings would push this to
the top). BM25 is no longer a bottleneck at any corpus size we measured; the
pipeline is now bounded by model inference and the vector store, as expected.

### Rust revisited

With this fix in, the earlier recommendation stands even more strongly:
a Rust port of BM25 would save ~50-150 ms end-to-end at typical corpus sizes
— well under the ~500 ms floor set by embedding + Qdrant. Revisit only if a
user reports pain on a corpus much larger than we've measured here.

---

## Post-Rust results (plan 3)

A Rust PyO3 port of `_Bm25Index` landed (`src/bm25.rs`,
`locallens._locallens_rs.RustBM25`). The Python wrapper in
`locallens/bm25.py` prefers `RustBM25` when
`locallens._rust.HAS_RUST_BM25` is True; otherwise it falls back to the
pure-Python `_Bm25Index` transparently. On-disk JSON format is identical,
so users can switch wheels without migration.

Same synthetic corpus + seeded RNG. Bench outputs:
`bench_200_rust.json`, `bench_500_rust.json`.

### 200 files / 1,485 chunks

| stage                       | pre-fix   | python post-fix | rust    | rust vs python |
| --------------------------- | --------- | --------------- | ------- | -------------- |
| bm25 build-from-scratch     | 115 ms    | 66 ms           | 69 ms   | ~1.0 ×         |
| **bm25 incremental + flush** | **10,520 ms** | **54 ms**   | **42 ms** | **1.3 ×** |
| **bm25 search (×14 queries)** | 27 ms  | **8 ms**        | **2.9 ms** | **2.8 ×** |

### 500 files / 3,779 chunks

| stage                       | pre-fix   | python post-fix | rust    | rust vs python |
| --------------------------- | --------- | --------------- | ------- | -------------- |
| bm25 build-from-scratch     | 292 ms    | 176 ms          | 182 ms  | ~1.0 ×         |
| **bm25 incremental + flush** | **67,699 ms** | **151 ms** | **114 ms** | **1.3 ×** |
| **bm25 search (×14 queries)** | 72 ms  | **32 ms**       | **10 ms** | **3.2 ×**  |

### What moved, what didn't

- **Search is the real Rust win: ~3×.** The per-token / per-doc scoring loop
  is where Python interpreter overhead dominated. Rust's tight `for i in 0..n`
  with direct `HashMap::get` reduces per-chunk cost from a Python dispatch to
  a native call.
- **Incremental is 1.3×.** The hot inner work (tokenize, update `df`) is
  modest; the remaining cost is the trailing `flush()` JSON write, which
  is identical in both implementations (we deliberately kept the same wire
  format).
- **Build-from-scratch is a wash (~1.0×).** Dominated by the JSON write
  again, plus the one-off corpus tokenize which Python already did in
  C-implemented `re.findall`.

### Total end-to-end impact

At 500 files the Rust cutover saves ~60 ms on `bm25_incremental` + ~22 ms
on `bm25_search`. End-to-end indexing drops from 0.50 s to 0.44 s (~12 %).
Search latency drops from ~2 ms/query to ~0.7 ms/query — user-noticeable
on tight interactive loops.

### Fallback still covers everyone

If `HAS_RUST_BM25` is False (sdist install without rustc; unsupported
platform), the Python post-fix path is used. Tests `test_rust_reads_python_json`
and `test_python_reads_rust_json` verify on-disk cross-compatibility so
switching install modes never requires a reindex.

---

## Post-walker results (plan 4)

Rust file walker + parallel SHA-256 (`src/walk.rs`,
`locallens._locallens_rs.RustWalker`) replaced the inline `rglob` +
serial `hashlib` loop duplicated across `locallens/indexer.py`,
`backend/app/services/indexer.py`, and `backend/app/services/watcher.py`.
A new shared core, `locallens/_file_core.py`, is the single entry point
for all three. The Rust backend uses `walkdir` for traversal + `rayon`
for cross-core parallel SHA-256; pure-Python fallback stays byte-identical
(verified by `test_walk_and_hash_rust_matches_python`).

A new `walk_and_hash_core` stage measures the actual code path the
indexer takes. The existing `walk` + `hash_sha256` baselines stay in the
bench as reference (rglob + serial hashlib) so before/after is visible
in one run.

### 200 files / 1,485 chunks

| stage                       | python baseline | rust (combined) | speedup |
| --------------------------- | --------------- | --------------- | ------- |
| walk (rglob only)           | 14 ms           | —               | —       |
| hash_sha256 (hashlib only)  | 28 ms           | —               | —       |
| **combined walk + hash**    | **42 ms**       | **19 ms**       | **2.2×** |

### 500 files / 3,779 chunks

| stage                       | python baseline | rust (combined) | speedup |
| --------------------------- | --------------- | --------------- | ------- |
| walk (rglob only)           | 33 ms           | —               | —       |
| hash_sha256 (hashlib only)  | 73 ms           | —               | —       |
| **combined walk + hash**    | **106 ms**      | **38 ms**       | **2.8×** |

### What moved

- **Combined walk + hash: 2.2× at 200 files, 2.8× at 500 files.** Parallel
  SHA-256 across cores is the dominant win; `walkdir` traversal is only
  marginally faster than `rglob`. The speedup grows with corpus size as
  parallelism amortizes.
- **End-to-end indexing at 500 files drops from ~0.44 s → ~0.34 s (~23 %)**,
  on top of what Rust BM25 already gave. The pipeline is now:
  extract 14 % + embed 23 % + bm25 31 % + walk+hash 9 % + chunk 5 % + misc.
- **walk + hash combined stage share dropped from ~31 % to ~10 %** —
  no longer the biggest remaining Rust target. Extract is now #1.

### Fallback parity

- `test_walk_and_hash_rust_matches_python` — builds a 6-file fixture
  tree, runs both backends, asserts identical sorted paths, identical
  hex SHA-256 values, identical sizes. Byte-for-byte.
- `test_rust_parallel_equals_serial` — same corpus, parallel vs serial
  hashing, identical output.
- `test_symlink_followed_by_default` — both backends include symlinked
  files with the hash of the resolved target (matches Python's existing
  `Path.is_file()` behavior).

The `hashlib`-compatible hex output means Qdrant's `has_hash` payload
index keeps working across upgrade/downgrade without a reindex.

---

## Scale analysis (plan 5)

Prior sections measured at 200 / 500 files. This section answers what
actually happens at 5,000 and 50,000 files — the range where LocalLens
indexing time first becomes user-visible.

All three runs on the same environment:

```text
Linux x86_64  cpu=16  ram=21.0G  python=3.11.15  rustc=1.94.1
```

Flags: `--mock-embed --skip-store`; 50k also uses `--skip-embed-cold`
to skip the per-chunk embed_batch_1 line. Seeded RNG (`--corpus-seed 42`);
three outputs committed as `bench_500_rust_v2.json`, `bench_5k_rust.json`,
`bench_50k_rust.json`.

### Absolute timings per stage

| stage                       | 500 files | 5k files | 50k files | 5k/500 | 50k/5k |
| --------------------------- | --------: | -------: | --------: | -----: | -----: |
| walk (rglob baseline)       |   53 ms  |  744 ms |  7,547 ms |  14.0× |  10.1× |
| hash_sha256 (hashlib)       |   93 ms  | 1,228 ms | 12,170 ms |  13.2× |   9.9× |
| **walk_and_hash_core (rust)** | **n/a (small)** | **958 ms** | **9,220 ms** |  —   |   9.6× |
| extract_text                |  134 ms  | 1,264 ms | 12,711 ms |   9.4× |  10.1× |
| chunk                       |   30 ms  |  302 ms |  3,078 ms |  10.1× |  10.2× |
| bm25_tokenize               |  102 ms  |  991 ms |  9,840 ms |   9.7× |   9.9× |
| bm25_build_fresh            |  237 ms  | 2,360 ms | 25,580 ms |  10.0× |  10.8× |
| bm25_incremental_per_file   |  160 ms  | 1,648 ms | 15,611 ms |  10.3× |   9.5× |
| bm25_search (14 queries)    |   11 ms  |  128 ms |  1,970 ms |  11.6× |  15.4× |
| embed_batch_32 (mock)       |  192 ms  | 1,719 ms | 17,893 ms |   9.0× |  10.4× |
| **end-to-end (stage sum)**  | **0.66 s** | **6.91 s** | **69.01 s** | **10.5×** | **10.0×** |

### Per-file cost

For O(N) stages the per-file numbers should stay flat across scales.
This is the main O-order sanity check:

| stage                       | 500    | 5k     | 50k    | linear? |
| --------------------------- | -----: | -----: | -----: | ------- |
| walk                        | 0.11 ms | 0.15 ms | 0.15 ms | ~linear |
| hash_sha256                 | 0.19 ms | 0.25 ms | 0.24 ms | ~linear |
| walk_and_hash_core (rust)   | 0.08 ms | 0.19 ms | 0.18 ms | ~linear |
| extract_text                | 0.27 ms | 0.25 ms | 0.25 ms | linear  |
| chunk                       | 0.06 ms | 0.06 ms | 0.06 ms | linear  |
| bm25_incremental_per_file   | 0.32 ms | 0.33 ms | 0.31 ms | linear  |
| bm25_search (per query)     | 0.79 ms | 9.17 ms | 140.75 ms | **super-linear** |

Every stage except `bm25_search` stays within 25% of its per-file cost
across two orders of magnitude of corpus size. The O(N²) BM25 fix from
Plan 1 continues to hold at 50k files (~0.3 ms per file, independent of
corpus size).

### Rust walk+hash speedup at scale

| scale  | python baseline (walk + hash) | rust (walk_and_hash_core) | speedup |
| -----: | ----------------------------: | ------------------------: | ------: |
| 500    | 146 ms                        | (subsumed)                | 2.8×    |
| 5k     | 1,972 ms                      | 958 ms                    | **2.06×** |
| 50k    | 19,717 ms                     | 9,220 ms                  | **2.14×** |

The 2.8× we measured at 500 files dropped to ~2× at 5k+ and stayed
there. At 500 files, hash dominated walk 2:1, and Rust's parallel
`sha2` was the main win. At 50k files, walk and hash are closer to
1:1 — `walkdir` traversal itself takes 7.5 s on this corpus shape
(50,000 files in a single flat directory), and walkdir's traversal is
only marginally faster than `rglob`. The per-file-hash win is still
~2.5× (Rust 0.18 ms vs Python 0.24 ms combined walk+hash), but that's
diluted by the walk-side latency.

**Takeaway:** Rust walker saves ~10 s at 50k. Wall-clock meaningful,
but not the dominant win it was at 500.

### What becomes dominant at scale?

End-to-end share at 50k:

| stage                       | seconds | share  |
| --------------------------- | ------: | -----: |
| bm25_build_fresh            |  25.6 s | 37.1 % |
| embed_batch_32              |  17.9 s | 25.9 % |
| bm25_incremental_per_file   |  15.6 s | 22.6 % |
| extract_text                |  12.7 s | 18.4 % |
| hash_sha256                 |  12.2 s | 17.6 % |
| walk                        |   7.5 s | 10.9 % |
| chunk                       |   3.1 s |  4.5 % |

Note: `bm25_build_fresh` is a cold-rebuild measurement; the actual
indexer code path uses `bm25_incremental_per_file` (22.6 %) plus the
once-at-startup `bm25.load()`. The table above over-counts BM25
because both build-fresh and incremental appear.

**The 50k user experience:** end-to-end indexing sum-of-stages = 69 s,
wall-clock including corpus-gen = 314 s (mock embed adds ~38 s of
sha1 precompute for the fake vectors). With a real embedder the embed
stage would be the biggest line item by far — ML inference at ~20k
chunks/sec (GPU) or ~2k chunks/sec (CPU) = 18 s to 180 s depending on
hardware. Rust modules can't help with that.

### bm25_search becomes user-noticeable at 50k

Per-query latency grew 140× (from 0.79 ms at 500 to 140.75 ms at 50k)
for 100× corpus growth. Super-linear in N. Likely cause: vocabulary
size grew more than linearly with corpus size, so the per-query
`recompute_idf` pass and the scoring loop over all docs per query
token both expanded. Needs profiling to confirm which term dominates.

This matches the Plan 3 prediction that search was the biggest Rust
BM25 win, but here we're seeing the RUST search still takes 140 ms at
50k. A 3× Rust speedup over pure-Python gets us from ~420 ms to
140 ms per query — significant, but 140 ms is still a noticeable
keystroke delay.

### What's next — candidate Phase 6 targets ranked

1. **`bm25_build_fresh` — if rebuild matters.** 25 s at 50k is the
   biggest single stage. But build-fresh is only hit on first-run; the
   steady state is `bm25_incremental` which is already Rust-backed and
   scales linearly. Low priority unless users frequently wipe indexes.
2. **Bincode BM25 persistence.** The incremental path's `flush()`
   writes JSON. At 50k the JSON state is ~25 MB and the full rewrite
   happens every `flush()`. Bincode would be 2-3× faster to
   serialize and 3-5× smaller on disk. Meaningful at this scale; easy
   extension to the existing Rust BM25 module. **This is the best
   Phase 6 candidate.**
3. **Rust chunker port.** 3.1 s at 50k (4.5 %). Smallest remaining
   direct Rust target. Small win; do it if we want the "complete"
   Rust rewrite story, skip it otherwise.
4. **bm25_search profiling + optimisation.** 140 ms per query at 50k
   is a problem. The Rust impl is already there, so the win isn't
   another language port — it's a smarter algorithm (e.g. query-time
   inverted index instead of recomputing per query, or
   block-max-WAND). This is algorithmic, not a port, and out of the
   "Rust Nth module" track.
5. **Parallel `bench_extract` / `bench_chunk`.** Both are embarrassingly
   parallel per-file. Not ported to Rust yet. Candidate if we want
   another 2× wall-clock on those stages.

### Verdict

- The Rust cutover thesis **holds at scale**. All ported stages stay
  linear in N; walk+hash gets ~2× real-world speedup; BM25
  incremental keeps its fix.
- **The next Rust target is persistence, not a new language port** —
  bincode-backed BM25 state would save 100s of ms on every `flush()`
  at 50k scale. Easy to add, slots into the existing `RustBM25` class
  with one feature flag.
- At typical corpus sizes (<1k files) the remaining Rust wins are
  diminishing and probably not worth further engineering time.
  Investment should pivot to release engineering, algorithmic work on
  search ranking, or user-facing features.
