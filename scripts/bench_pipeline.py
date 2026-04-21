"""Benchmark the LocalLens indexing + search pipeline, stage by stage.

Generates a synthetic corpus, then times each hot path independently so we can
see where wall-clock time is actually spent before considering Rust rewrites.

Run:
    uv run python scripts/bench_pipeline.py [--files N] [--out report.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

from locallens.pipeline import bm25 as bm25_mod
from locallens.pipeline import store as store_mod
from locallens.pipeline.chunker import chunk_text

try:
    from locallens.pipeline.embedder import embed_query, embed_texts  # noqa: F401

    _EMBEDDER_AVAILABLE = True
except Exception:
    _EMBEDDER_AVAILABLE = False


def _mock_embed_texts(texts):
    """Deterministic 384-dim vectors derived from sha1(text) bytes.

    Not a real embedding — just the right *shape* so we can bench the
    non-ML stages (upsert, search, bm25) without needing HF access.
    """
    import numpy as np

    out = []
    for t in texts:
        h = hashlib.sha1(t.encode("utf-8", errors="ignore")).digest()
        # Tile the 20-byte digest to 384 floats, normalize to unit length.
        rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
        v = rng.standard_normal(384, dtype=np.float32)
        v /= np.linalg.norm(v) + 1e-12
        out.append(v.tolist())
    return out


def _mock_embed_query(text):
    return _mock_embed_texts([text])[0]


# ----------------------------------------------------------------------------
# Synthetic corpus generation
# ----------------------------------------------------------------------------

LOREM = (
    "the quick brown fox jumps over the lazy dog pack my box with five dozen "
    "liquor jugs sphinx of black quartz judge my vow how vexingly quick daft "
    "zebras jump bright vixens jump dozy fowl quack amazingly few discotheques "
    "provide jukeboxes waltz nymph for quick jigs vex bud jackdaws love my big "
    "sphinx of quartz the five boxing wizards jump quickly "
)

TOPICS = [
    "machine learning",
    "database indexing",
    "vector search",
    "rust programming",
    "python performance",
    "distributed systems",
    "offline-first apps",
    "tokenization",
    "embedding models",
    "BM25 ranking",
    "compiler design",
    "semantic retrieval",
    "chunk overlap",
    "cosine similarity",
]


def _paragraph(rng: random.Random, size: int) -> str:
    """Build a paragraph roughly `size` chars long, seeded with topic words."""
    words: list[str] = []
    total = 0
    topic = rng.choice(TOPICS)
    while total < size:
        w = rng.choice(LOREM.split())
        if rng.random() < 0.05:
            w = topic.split()[rng.randrange(len(topic.split()))]
        words.append(w)
        total += len(w) + 1
    return " ".join(words) + "."


def make_markdown(rng: random.Random, sections: int = 6, para_size: int = 400) -> str:
    out: list[str] = []
    for i in range(sections):
        out.append(f"# Section {i + 1}: {rng.choice(TOPICS).title()}")
        for _ in range(rng.randint(2, 4)):
            out.append(_paragraph(rng, para_size))
            out.append("")
    return "\n".join(out)


def make_python(rng: random.Random, n_funcs: int = 8) -> str:
    lines: list[str] = []
    for i in range(n_funcs):
        name = f"compute_{rng.choice(TOPICS).replace(' ', '_')}_{i}"
        lines.append(f"def {name}(x, y):")
        lines.append(f'    """{_paragraph(rng, 120)}"""')
        lines.append("    total = 0")
        for _ in range(rng.randint(4, 10)):
            lines.append(f"    total += x * {rng.randint(1, 99)} + y")
        lines.append("    return total")
        lines.append("")
    return "\n".join(lines)


def make_plain_text(
    rng: random.Random, paragraphs: int = 5, para_size: int = 600
) -> str:
    return "\n\n".join(_paragraph(rng, para_size) for _ in range(paragraphs))


def generate_corpus(root: Path, n_files: int, rng: random.Random) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(n_files):
        kind = rng.choices(["md", "txt", "py"], weights=[0.5, 0.3, 0.2])[0]
        if kind == "md":
            content = make_markdown(rng, sections=rng.randint(3, 8))
            path = root / f"doc_{i:04d}.md"
        elif kind == "txt":
            content = make_plain_text(rng, paragraphs=rng.randint(3, 8))
            path = root / f"note_{i:04d}.txt"
        else:
            content = make_python(rng, n_funcs=rng.randint(4, 12))
            path = root / f"mod_{i:04d}.py"
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


# ----------------------------------------------------------------------------
# Benchmark primitives
# ----------------------------------------------------------------------------


@dataclass
class StageResult:
    stage: str
    seconds: float
    items: int
    note: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def per_item_ms(self) -> float:
        return (self.seconds / self.items * 1000.0) if self.items else 0.0

    def row(self) -> dict:
        return {
            "stage": self.stage,
            "seconds": round(self.seconds, 4),
            "items": self.items,
            "per_item_ms": round(self.per_item_ms, 3),
            "note": self.note,
            **self.extra,
        }


def time_it(fn, *args, **kwargs) -> tuple[float, object]:
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    return time.perf_counter() - t0, out


def _total_ram_bytes() -> int:
    """Cross-platform best-effort total RAM probe for the env summary."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        pass
    try:
        import psutil  # type: ignore[import-not-found]

        return int(psutil.virtual_memory().total)
    except Exception:
        return 0


def _try_cmd(argv: list[str]) -> str:
    """Run `argv` and return its first line of stdout, or 'not-installed' on failure."""
    import subprocess

    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=2)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "not-installed"
    return (
        (out.stdout or out.stderr).strip().splitlines()[0]
        if (out.stdout or out.stderr)
        else "unknown"
    )


# ----------------------------------------------------------------------------
# Stage benchmarks
# ----------------------------------------------------------------------------


def bench_walk(root: Path) -> StageResult:
    t0 = time.perf_counter()
    files = [p for p in root.rglob("*") if p.is_file()]
    dt = time.perf_counter() - t0
    return StageResult("walk", dt, len(files), note="rglob + is_file filter")


def bench_hash(paths: list[Path]) -> StageResult:
    t0 = time.perf_counter()
    total_bytes = 0
    for p in paths:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
                total_bytes += len(block)
        h.hexdigest()
    dt = time.perf_counter() - t0
    return StageResult(
        "hash_sha256",
        dt,
        len(paths),
        extra={
            "mb_per_sec": round(total_bytes / 1024 / 1024 / dt, 2) if dt else 0.0,
            "total_mb": round(total_bytes / 1024 / 1024, 2),
        },
    )


def bench_walk_and_hash_core(
    root: Path, extensions: frozenset[str], max_file_size_bytes: int
) -> StageResult:
    """Measures the actual code path indexer.py now takes — Rust when
    HAS_RUST_WALKER, Python otherwise. Reported as a separate stage so
    before/after is visible alongside the rglob + hashlib baseline."""
    from locallens._internals._file_core import walk_and_hash
    from locallens._internals._rust import HAS_RUST_WALKER

    t0 = time.perf_counter()
    entries = walk_and_hash(root, extensions, max_file_size_bytes=max_file_size_bytes)
    dt = time.perf_counter() - t0
    total_bytes = sum(e.size for e in entries)
    return StageResult(
        "walk_and_hash_core",
        dt,
        len(entries),
        note=f"backend={'rust' if HAS_RUST_WALKER else 'python'}",
        extra={
            "mb_per_sec": round(total_bytes / 1024 / 1024 / dt, 2) if dt else 0.0,
            "total_mb": round(total_bytes / 1024 / 1024, 2),
        },
    )


def bench_extract(paths: list[Path]) -> tuple[StageResult, list[str]]:
    # Just use plain read for .md/.txt/.py (matches TextExtractor/CodeExtractor).
    texts: list[str] = []
    t0 = time.perf_counter()
    for p in paths:
        texts.append(p.read_text(encoding="utf-8", errors="ignore"))
    dt = time.perf_counter() - t0
    total_chars = sum(len(t) for t in texts)
    return StageResult(
        "extract_text",
        dt,
        len(paths),
        extra={
            "mchars_per_sec": round(total_chars / 1_000_000 / dt, 2) if dt else 0.0,
            "total_mchars": round(total_chars / 1_000_000, 2),
        },
    ), texts


def bench_chunk(
    paths: list[Path], texts: list[str]
) -> tuple[StageResult, list[list[str]]]:
    chunks_all: list[list[str]] = []
    t0 = time.perf_counter()
    for p, txt in zip(paths, texts):
        chunks_all.append(chunk_text(txt, 1000, 50, file_type=p.suffix.lower()))
    dt = time.perf_counter() - t0
    n_chunks = sum(len(c) for c in chunks_all)
    return StageResult(
        "chunk",
        dt,
        len(paths),
        extra={
            "total_chunks": n_chunks,
            "avg_chunks_per_file": round(n_chunks / max(len(paths), 1), 2),
        },
    ), chunks_all


def bench_embed_cold(sample_chunks: list[str]) -> StageResult:
    # Cold start: first call loads the model.
    t0 = time.perf_counter()
    embed_texts(sample_chunks[:1])
    dt = time.perf_counter() - t0
    return StageResult(
        "embed_model_load_+_1chunk", dt, 1, note="first call, loads model"
    )


def bench_embed_batched(chunks_all: list[list[str]], batch_size: int) -> StageResult:
    flat = [c for cs in chunks_all for c in cs]
    t0 = time.perf_counter()
    for i in range(0, len(flat), batch_size):
        embed_texts(flat[i : i + batch_size])
    dt = time.perf_counter() - t0
    return StageResult(
        f"embed_batch_{batch_size}",
        dt,
        len(flat),
        note="warm model",
        extra={"chunks_per_sec": round(len(flat) / dt, 1) if dt else 0.0},
    )


def bench_embed_query(n: int = 20) -> StageResult:
    queries = [f"what is {t}" for t in TOPICS[:n]]
    # warm-up
    embed_query("warmup")
    t0 = time.perf_counter()
    for q in queries:
        embed_query(q)
    dt = time.perf_counter() - t0
    return StageResult(
        "embed_query",
        dt,
        len(queries),
        extra={"queries_per_sec": round(len(queries) / dt, 1) if dt else 0.0},
    )


def bench_bm25_build_fresh(
    chunks_all: list[list[str]], paths: list[Path]
) -> StageResult:
    # Fresh build: all docs at once (what build_index does).
    docs: list[dict] = []
    for p, cs in zip(paths, chunks_all):
        for i, c in enumerate(cs):
            docs.append({"id": f"{p}:{i}", "chunk_text": c})
    t0 = time.perf_counter()
    bm25_mod.build_index(docs)
    dt = time.perf_counter() - t0
    return StageResult(
        "bm25_build_fresh",
        dt,
        len(docs),
        note="build_index(all_docs)",
        extra={"docs_per_sec": round(len(docs) / dt, 1) if dt else 0.0},
    )


def bench_bm25_incremental(
    chunks_all: list[list[str]], paths: list[Path]
) -> StageResult:
    # Simulate what indexer.py does: call add_documents once per file, then
    # flush at the end (matches locallens/indexer.py and backend lifespan).
    # The pre-fix path persisted on every add_documents call, so for a
    # like-for-like comparison the post-fix measurement must include flush.
    bm25_mod.build_index([])
    t0 = time.perf_counter()
    for p, cs in zip(paths, chunks_all):
        docs = [{"id": f"{p}:{i}", "chunk_text": c} for i, c in enumerate(cs)]
        bm25_mod.add_documents(docs)
    bm25_mod.flush()
    dt = time.perf_counter() - t0
    total_chunks = sum(len(c) for c in chunks_all)
    return StageResult(
        "bm25_incremental_per_file",
        dt,
        len(paths),
        note="indexer.py path: add_documents() per file + final flush()",
        extra={
            "total_chunks": total_chunks,
            "files_per_sec": round(len(paths) / dt, 2) if dt else 0.0,
        },
    )


def bench_bm25_search(queries: list[str], top_k: int = 10) -> StageResult:
    t0 = time.perf_counter()
    for q in queries:
        bm25_mod.search(q, top_k=top_k)
    dt = time.perf_counter() - t0
    return StageResult(
        "bm25_search",
        dt,
        len(queries),
        extra={"queries_per_sec": round(len(queries) / dt, 1) if dt else 0.0},
    )


def bench_bm25_tokenize(chunks_all: list[list[str]]) -> StageResult:
    import re

    flat = [c for cs in chunks_all for c in cs]
    tok_re = re.compile(r"\w+")
    t0 = time.perf_counter()
    total_tokens = 0
    for c in flat:
        total_tokens += len(tok_re.findall(c.lower()))
    dt = time.perf_counter() - t0
    return StageResult(
        "bm25_tokenize",
        dt,
        len(flat),
        extra={
            "total_tokens": total_tokens,
            "tokens_per_sec": round(total_tokens / dt, 0) if dt else 0.0,
        },
    )


def bench_store_upsert(
    chunks_all: list[list[str]], paths: list[Path], embeddings: list[list[float]]
) -> StageResult:
    # Build points shaped like indexer.py does.
    from locallens.pipeline.indexer import UUID_NAMESPACE

    store_mod.init()

    def _point_id(path: str, i: int) -> str:
        return str(uuid.uuid5(UUID_NAMESPACE, f"{path}:{i}"))

    all_points: list[dict] = []
    emb_iter = iter(embeddings)
    for p, cs in zip(paths, chunks_all):
        abs_p = str(p.resolve())
        for i, c in enumerate(cs):
            emb = next(emb_iter)
            all_points.append(
                {
                    "id": _point_id(abs_p, i),
                    "vector": list(emb),
                    "payload": {
                        "file_path": abs_p,
                        "file_name": p.name,
                        "file_type": p.suffix.lower(),
                        "chunk_index": i,
                        "chunk_text": c,
                        "file_hash": "bench",
                        "indexed_at": "2026-01-01T00:00:00+00:00",
                        "extractor": "bench",
                        "page_number": None,
                        "file_modified_at": None,
                    },
                }
            )
    t0 = time.perf_counter()
    store_mod.upsert_batch(all_points)
    dt = time.perf_counter() - t0
    return StageResult(
        "qdrant_edge_upsert",
        dt,
        len(all_points),
        extra={"points_per_sec": round(len(all_points) / dt, 1) if dt else 0.0},
    )


def bench_store_has_hash(paths: list[Path]) -> StageResult:
    # Measure the per-file dedup lookup (O(1) payload-index check).
    h = hashlib.sha256(b"nonexistent-bench").hexdigest()
    t0 = time.perf_counter()
    for _ in paths:
        store_mod.has_hash(h)
    dt = time.perf_counter() - t0
    return StageResult(
        "qdrant_edge_has_hash",
        dt,
        len(paths),
        extra={"lookups_per_sec": round(len(paths) / dt, 1) if dt else 0.0},
    )


def bench_store_search(queries_vec: list[list[float]], top_k: int = 10) -> StageResult:
    t0 = time.perf_counter()
    for v in queries_vec:
        store_mod.search(v, top_k=top_k)
    dt = time.perf_counter() - t0
    return StageResult(
        "qdrant_edge_search",
        dt,
        len(queries_vec),
        extra={"queries_per_sec": round(len(queries_vec) / dt, 1) if dt else 0.0},
    )


# ----------------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------------


def human_seconds(s: float) -> str:
    if s < 1e-3:
        return f"{s * 1e6:.1f} µs"
    if s < 1.0:
        return f"{s * 1000:.1f} ms"
    return f"{s:.2f} s"


def print_table(results: list[StageResult]) -> None:
    print()
    print(f"{'stage':<35} {'time':>10} {'items':>8} {'per-item':>12}   extra")
    print("-" * 110)
    for r in results:
        extras = " ".join(f"{k}={v}" for k, v in r.extra.items())
        print(
            f"{r.stage:<35} {human_seconds(r.seconds):>10} {r.items:>8d} "
            f"{r.per_item_ms:>10.3f} ms   {extras}"
        )
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=200, help="synthetic file count")
    ap.add_argument("--out", type=str, default=None, help="optional JSON report path")
    ap.add_argument(
        "--corpus", type=str, default=None, help="reuse existing corpus dir"
    )
    ap.add_argument(
        "--corpus-seed",
        type=int,
        default=42,
        help="RNG seed for the synthetic corpus (default: 42)",
    )
    ap.add_argument("--skip-store", action="store_true", help="skip Qdrant Edge stages")
    ap.add_argument("--skip-embed", action="store_true", help="skip embedding stages")
    ap.add_argument(
        "--skip-embed-cold",
        action="store_true",
        help="skip the batch_size=1 per-chunk embed line (saves ~30s at 50k files)",
    )
    ap.add_argument(
        "--mock-embed",
        action="store_true",
        help="use deterministic fake 384-dim vectors (for bench only, no ML)",
    )
    args = ap.parse_args()

    # One-line hardware summary so numbers are comparable across machines.
    try:
        import platform

        cpu_count = os.cpu_count() or 1
        mem_gb = round(_total_ram_bytes() / (1024**3), 1)
        rustc = _try_cmd(["rustc", "--version"])
        print(
            f"[env] {platform.system()} {platform.machine()} "
            f"cpu={cpu_count} ram={mem_gb}G "
            f"python={platform.python_version()} rustc={rustc}"
        )
    except Exception as exc:
        print(f"[env] (could not probe host: {exc})")

    wallclock_start = time.perf_counter()

    # Patch in a mock embedder when requested (or when the real one is unavailable).
    if args.mock_embed or not _EMBEDDER_AVAILABLE:
        globals()["embed_texts"] = _mock_embed_texts
        globals()["embed_query"] = _mock_embed_query
        args.mock_embed = True
        print("[embed] using MOCK embedder (384-dim vectors derived from sha1)")

    rng = random.Random(args.corpus_seed)

    tmp_root = tempfile.mkdtemp(prefix="locallens_bench_")
    if args.corpus:
        corpus = Path(args.corpus)
        paths = sorted(p for p in corpus.rglob("*") if p.is_file())
        print(f"[corpus] reusing {corpus} with {len(paths)} files")
    else:
        corpus = Path(tmp_root) / "corpus"
        print(f"[corpus] generating {args.files} files in {corpus}")
        paths = generate_corpus(corpus, args.files, rng)

    # Point the store & bm25 at an isolated path so we don't touch user data.
    bench_lens_home = Path(tmp_root) / "locallens_home"
    bench_lens_home.mkdir(parents=True, exist_ok=True)
    bm25_mod._set_persist_path(bench_lens_home / "bm25_index.json")
    # store uses locallens.config.QDRANT_PATH — override via the store module.
    from locallens import config as cfg

    cfg.QDRANT_PATH = bench_lens_home / "qdrant_data"
    store_mod.QDRANT_PATH = cfg.QDRANT_PATH
    # Force shard reset.
    store_mod._shard = None

    results: list[StageResult] = []

    # 1. walk (baseline: rglob + is_file)
    results.append(bench_walk(corpus))

    # 2. hash (baseline: hashlib streaming, serial)
    results.append(bench_hash(paths))

    # 2b. combined walk + hash via the shared _file_core path — Rust when
    # HAS_RUST_WALKER is True. This is what indexer.py actually runs.
    from locallens.config import MAX_FILE_SIZE_MB, SUPPORTED_EXTENSIONS

    results.append(
        bench_walk_and_hash_core(
            corpus,
            frozenset(SUPPORTED_EXTENSIONS),
            MAX_FILE_SIZE_MB * 1024 * 1024,
        )
    )

    # 3. extract (plain read for .md/.txt/.py)
    extract_result, texts = bench_extract(paths)
    results.append(extract_result)

    # 4. chunk
    chunk_result, chunks_all = bench_chunk(paths, texts)
    results.append(chunk_result)

    flat_chunks = [c for cs in chunks_all for c in cs]
    print(f"[chunks] total chunks: {len(flat_chunks)}")

    # 5. BM25 tokenize alone
    results.append(bench_bm25_tokenize(chunks_all))

    # 6. BM25 fresh build
    results.append(bench_bm25_build_fresh(chunks_all, paths))

    # 7. BM25 incremental (indexer.py path — the O(n^2) problem)
    results.append(bench_bm25_incremental(chunks_all, paths))

    # 8. BM25 search
    queries = [f"what is {t}" for t in TOPICS]
    results.append(bench_bm25_search(queries))

    embeddings: list[list[float]] = []

    if not args.skip_embed:
        if not args.mock_embed:
            # 9. embedding cold start (only meaningful for the real model)
            results.append(bench_embed_cold(flat_chunks))

        # 10. embedding warm, batched
        embed_batch_sizes = (1, 8, 32, 64)
        if args.skip_embed_cold:
            embed_batch_sizes = tuple(bs for bs in embed_batch_sizes if bs != 1)
        for bs in embed_batch_sizes:
            r = bench_embed_batched(chunks_all, batch_size=bs)
            if args.mock_embed:
                r.note = "MOCK (not real ML timing)"
            results.append(r)

        # 11. query embedding (single)
        r = bench_embed_query(n=len(TOPICS))
        if args.mock_embed:
            r.note = "MOCK (not real ML timing)"
        results.append(r)

        # precompute embeddings for store tests (batch 32 is the natural size)
        print("[precompute] embedding all chunks (batch=32) for store benches…")
        t0 = time.perf_counter()
        for i in range(0, len(flat_chunks), 32):
            embeddings.extend(embed_texts(flat_chunks[i : i + 32]))
        print(f"[precompute] done in {time.perf_counter() - t0:.2f}s")

    if not args.skip_store and embeddings:
        # 12. qdrant edge upsert (single large batch)
        results.append(bench_store_upsert(chunks_all, paths, embeddings))

        # 13. qdrant edge has_hash
        results.append(bench_store_has_hash(paths))

        # 14. qdrant edge search
        qvecs = []
        for t in TOPICS:
            qvecs.append(embed_query(f"what is {t}"))
        results.append(bench_store_search(qvecs))

    print_table(results)

    # Summary: stage share of an end-to-end index run.
    # Approximate full pipeline = walk + hash + extract + chunk + bm25_incremental + embed_batch_32 + qdrant_upsert.
    stage_map = {r.stage: r for r in results}
    end_to_end_stages = [
        "walk",
        "hash_sha256",
        "extract_text",
        "chunk",
        "bm25_incremental_per_file",
        "embed_batch_32",
        "qdrant_edge_upsert",
    ]
    total = sum(stage_map[s].seconds for s in end_to_end_stages if s in stage_map)
    wallclock_total = time.perf_counter() - wallclock_start
    print(
        f"End-to-end index (sum of stages): {total:.2f}s for {len(paths)} files, {len(flat_chunks)} chunks"
    )
    print(f"Wall-clock including corpus gen + all stages: {wallclock_total:.2f}s")
    print(f"{'stage':<35} {'seconds':>10} {'share':>8}")
    print("-" * 60)
    for s in end_to_end_stages:
        r = stage_map.get(s)
        if not r:
            continue
        share = (r.seconds / total * 100.0) if total else 0.0
        print(f"{s:<35} {r.seconds:>10.3f} {share:>7.1f}%")
    print()

    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {
                    "n_files": len(paths),
                    "n_chunks": len(flat_chunks),
                    "results": [r.row() for r in results],
                    "end_to_end_total_s": total,
                    "wallclock_total_s": round(wallclock_total, 3),
                },
                indent=2,
            )
        )
        print(f"[report] wrote {args.out}")


if __name__ == "__main__":
    main()
