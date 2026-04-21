"""Direct unit tests for the BM25 core + both wrapper modules.

Each test is explicitly tied to a bug class it prevents. See
``bench-results/FINDINGS.md`` for the benchmark that motivated these.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import pytest
from rank_bm25 import BM25Okapi

from locallens._internals._bm25_core import _Bm25Index, _tokenize

FIXED_CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "pack my box with five dozen liquor jugs",
    "sphinx of black quartz judge my vow",
    "how vexingly quick daft zebras jump",
    "bright vixens jump dozy fowl quack",
    "amazingly few discotheques provide jukeboxes",
    "the five boxing wizards jump quickly",
    "jackdaws love my big sphinx of quartz",
    "the quick brown dog runs over the lazy cat",
    "fast foxes and lazy dogs share a meadow",
    "quartz glass sparkles in the morning light",
    "dogs and cats live together peacefully",
    "rapid typing requires a calm mind",
    "indexing documents efficiently matters",
    "semantic search complements keyword search",
    "hybrid ranking uses reciprocal rank fusion",
    "offline tools protect personal privacy",
    "a fox in the henhouse is a disaster",
    "the lazy cat ignored the busy fox",
    "wizards of light jump through hoops",
]


def _make_docs(texts: list[str], start: int = 0) -> list[dict]:
    """Build doc dicts with a stable ``d{index}`` id. ``start`` is the offset
    into the caller's master list so that ``_make_docs(FIXED_CORPUS[3:4],
    start=3)`` produces ``d3`` — matching ``_make_docs(FIXED_CORPUS[:4])``'s
    4th entry, not colliding with its first."""
    return [{"id": f"d{i}", "chunk_text": t} for i, t in enumerate(texts, start=start)]


def _rank_bm25_scores(corpus: list[str], query: str) -> list[float]:
    """Reference scores from rank_bm25 for parity checks."""
    tokenized = [_tokenize(t) for t in corpus]
    bm = BM25Okapi(tokenized)
    return list(bm.get_scores(_tokenize(query)))


@pytest.fixture
def idx(tmp_path: Path) -> _Bm25Index:
    return _Bm25Index(tmp_path / "bm25.json")


# ----------------------------------------------------------------------
# 1 + 2 — Parity with rank_bm25 (prevents silent ranking / score drift)
# ----------------------------------------------------------------------


def test_build_index_matches_rank_bm25_ranking(idx: _Bm25Index) -> None:
    idx.build_index(_make_docs(FIXED_CORPUS))
    for query in ["fox", "lazy dog", "sphinx quartz", "jump", "indexing search"]:
        ref = _rank_bm25_scores(FIXED_CORPUS, query)
        ref_ranked = sorted(
            [(f"d{i}", s) for i, s in enumerate(ref) if s > 0],
            key=lambda x: x[1],
            reverse=True,
        )
        ours = idx.search(query, top_k=len(FIXED_CORPUS))
        # Compare the ordered doc_ids — ranking equality is the contract.
        assert [d for d, _ in ours] == [d for d, _ in ref_ranked], (
            f"ranking mismatch for query {query!r}: ours={ours} ref={ref_ranked}"
        )


def test_score_parity_within_epsilon(idx: _Bm25Index) -> None:
    idx.build_index(_make_docs(FIXED_CORPUS))
    for query in ["fox", "lazy dog", "sphinx quartz"]:
        ref = _rank_bm25_scores(FIXED_CORPUS, query)
        ours = dict(idx.search(query, top_k=len(FIXED_CORPUS)))
        for i, ref_score in enumerate(ref):
            if ref_score <= 0:
                continue
            our_score = ours.get(f"d{i}")
            assert our_score is not None, f"missing d{i} for query {query!r}"
            assert abs(our_score - ref_score) < 1e-9, (
                f"score mismatch for d{i} query={query!r}: "
                f"ours={our_score} ref={ref_score}"
            )


# ----------------------------------------------------------------------
# 3 — Incremental df update (prevents rebuild-on-every-add regression)
# ----------------------------------------------------------------------


def test_add_updates_df_incrementally(tmp_path: Path) -> None:
    idx_a = _Bm25Index(tmp_path / "a.json")
    idx_a.build_index(_make_docs(FIXED_CORPUS[:3]))
    idx_a.add_documents(_make_docs(FIXED_CORPUS[3:4], start=3))

    idx_b = _Bm25Index(tmp_path / "b.json")
    idx_b.build_index(_make_docs(FIXED_CORPUS[:4]))

    assert idx_a.state.df == idx_b.state.df
    assert idx_a.state.total_tokens == idx_b.state.total_tokens
    assert idx_a.state.doc_lengths == idx_b.state.doc_lengths


# ----------------------------------------------------------------------
# 4 — Linearity (prevents the exact O(N^2) bug we're fixing)
# ----------------------------------------------------------------------


def _time_add(idx: _Bm25Index, start: int, n: int) -> float:
    t0 = time.perf_counter()
    for i in range(start, start + n):
        idx.add_documents(
            [
                {
                    "id": f"s{i}",
                    "chunk_text": f"document number {i} with some filler text",
                }
            ]
        )
    return time.perf_counter() - t0


def test_add_is_linear_not_quadratic(tmp_path: Path) -> None:
    """Assert scaling is linear-ish by comparing two run sizes.

    O(N) adds → elapsed_500 / elapsed_50 ≈ 10×
    O(N²) adds → elapsed_500 / elapsed_50 ≈ 100× (pre-fix actual was ~120×)

    A threshold of 30× leaves plenty of headroom for noise on slow CI while
    still catching a quadratic regression.  An env var lets operators raise
    the threshold on exceptionally slow machines without patching the code.
    """
    idx = _Bm25Index(tmp_path / "scale.json")
    idx.build_index([])

    baseline = _time_add(idx, start=0, n=50)
    big = _time_add(idx, start=50, n=500)

    # Protect against divide-by-near-zero on ludicrously fast hardware.
    baseline_floor = max(baseline, 1e-4)
    ratio = big / baseline_floor
    max_ratio = float(os.environ.get("BM25_LINEARITY_MAX_RATIO", "30"))

    assert ratio < max_ratio, (
        f"O(N^2) regression: 500 adds took {big:.3f}s vs 50-add baseline "
        f"{baseline:.3f}s (ratio={ratio:.1f}x, threshold={max_ratio:.1f}x). "
        "Linear scaling would be ~10x."
    )


# ----------------------------------------------------------------------
# 5 — Remove recomputes idf (prevents stale idf after removal)
# ----------------------------------------------------------------------


def test_remove_recomputes_idf(idx: _Bm25Index) -> None:
    idx.build_index(_make_docs(FIXED_CORPUS))
    pre = dict(idx.search("sphinx", top_k=20))
    assert pre, "expected 'sphinx' to match at least one doc pre-removal"

    # Remove every doc that contains 'sphinx'.
    to_remove = [
        f"d{i}" for i, text in enumerate(FIXED_CORPUS) if "sphinx" in text.lower()
    ]
    assert to_remove, "test precondition: corpus must contain 'sphinx'"
    idx.remove_documents(to_remove)

    post = idx.search("sphinx", top_k=20)
    assert post == [], f"expected empty search post-removal, got {post}"


# ----------------------------------------------------------------------
# 6 — In-place update (prevents df double-count on id replacement)
# ----------------------------------------------------------------------


def test_update_existing_doc_id(idx: _Bm25Index) -> None:
    # Background corpus so rare terms ('alpha'/'delta') get positive idf.
    idx.build_index(_make_docs(FIXED_CORPUS))
    before_n = len(idx.state.doc_ids)

    idx.add_documents([{"id": "foo", "chunk_text": "alpha beta gamma"}])
    assert idx.search("alpha", top_k=5), "alpha should match before overwrite"
    assert idx.search("delta", top_k=5) == []

    idx.add_documents([{"id": "foo", "chunk_text": "delta epsilon zeta"}])
    assert idx.search("alpha", top_k=5) == [], "alpha must not match after overwrite"
    assert idx.search("delta", top_k=5), "delta should match after overwrite"
    # The 'foo' replacement should leave doc-count unchanged at background + 1.
    assert len(idx.state.doc_ids) == before_n + 1


# ----------------------------------------------------------------------
# 7 — Old-format JSON loads unchanged (prevents breaking existing indexes)
# ----------------------------------------------------------------------


def test_load_forward_compatible_with_old_json(tmp_path: Path) -> None:
    """Write a file in the exact shape the pre-fix code produced, then load it.
    The on-disk schema is unchanged post-fix, so this is a no-migration test."""
    path = tmp_path / "old.json"
    path.write_text(
        json.dumps(
            {
                "doc_ids": [f"d{i}" for i in range(len(FIXED_CORPUS))],
                "corpus_texts": list(FIXED_CORPUS),
            }
        )
    )
    idx = _Bm25Index(path)
    idx.load()
    assert idx.is_loaded()
    # 'sphinx' appears in 2 of the 20 docs — idf is positive, so hits is non-empty.
    hits = idx.search("sphinx", top_k=5)
    assert hits, "expected 'sphinx' to match after loading old-format JSON"


# ----------------------------------------------------------------------
# 8 — Deferred flush + atexit safety
# ----------------------------------------------------------------------


def test_flush_is_deferred_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "defer.json"
    idx = _Bm25Index(path)
    # build_index is eager — gives us a baseline file on disk.
    idx.build_index(_make_docs(FIXED_CORPUS[:2]))
    baseline_mtime = path.stat().st_mtime_ns

    # Sleep briefly so the fs timestamp resolution can register a change
    # when/if it happens. Most linux fs have ns resolution; this is belt +
    # suspenders on exotic targets.
    time.sleep(0.01)

    # Deferred mutation: file mtime should NOT change.
    idx.add_documents(_make_docs(FIXED_CORPUS[2:4]))
    assert path.stat().st_mtime_ns == baseline_mtime, "add_documents must defer"

    idx.flush()
    after_flush_mtime = path.stat().st_mtime_ns
    assert after_flush_mtime > baseline_mtime, "flush must persist"

    # Idempotent — second flush does nothing harmful.
    idx.flush()
    assert path.stat().st_mtime_ns == after_flush_mtime


# ----------------------------------------------------------------------
# 9 — Env escape hatch for eager persistence (debuggability)
# ----------------------------------------------------------------------


def test_eager_flush_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALLENS_BM25_EAGER_FLUSH", "1")
    path = tmp_path / "eager.json"
    idx = _Bm25Index(path)
    idx.add_documents(_make_docs(FIXED_CORPUS[:1]))
    assert path.exists(), "eager mode must persist on every mutation"
    first_mtime = path.stat().st_mtime_ns

    time.sleep(0.01)
    idx.add_documents(_make_docs(FIXED_CORPUS[1:2]))
    assert path.stat().st_mtime_ns > first_mtime


# ----------------------------------------------------------------------
# 10 — CLI and backend wrappers share the same core type
# ----------------------------------------------------------------------


def test_cli_and_backend_share_core() -> None:
    from backend.app.services import bm25 as backend_bm25
    from locallens.pipeline import bm25 as cli_bm25

    assert type(cli_bm25._index) is type(backend_bm25._index)


# ----------------------------------------------------------------------
# Wrapper-module sanity — _set_persist_path works end to end
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Rust parity — prevents Rust / Python ranking or persistence drift.
# Skipped automatically when the Rust extension isn't built.
# ----------------------------------------------------------------------


_RUST_IMPORT_REASON = "Rust extension (locallens._locallens_rs) not built"


def _get_rust_cls():
    """Import RustBM25 lazily so the rest of the file loads without Rust.

    Catches only ``ModuleNotFoundError``: any other ``ImportError`` (ABI
    mismatch, missing symbol, etc.) indicates the extension is present but
    broken, which should fail CI rather than silently skip the tests.
    """
    try:
        from locallens._locallens_rs import RustBM25  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        pytest.skip(_RUST_IMPORT_REASON)
    return RustBM25


def test_rust_python_search_parity(tmp_path: Path) -> None:
    """Rust and Python implementations must produce identical rankings and
    scores for the same corpus + query. Prevents silent divergence."""
    RustBM25 = _get_rust_cls()

    py_idx = _Bm25Index(tmp_path / "py.json")
    rs_idx = RustBM25(str(tmp_path / "rs.json"))

    docs = _make_docs(FIXED_CORPUS)
    py_idx.build_index(docs)
    rs_idx.build_index(docs)

    queries = [
        "fox",
        "lazy dog",
        "sphinx quartz",
        "jump",
        "indexing search",
        "wizards jump",
        "quick brown",
        "discotheques",
        "cats dogs",
        "morning light",
    ]
    for q in queries:
        py_hits = py_idx.search(q, top_k=len(FIXED_CORPUS))
        rs_hits = rs_idx.search(q, top_k=len(FIXED_CORPUS))
        assert [d for d, _ in py_hits] == [d for d, _ in rs_hits], (
            f"ranking diverged for {q!r}: py={py_hits} rs={rs_hits}"
        )
        for (pid, ps), (rid, rs) in zip(py_hits, rs_hits):
            assert pid == rid
            assert abs(ps - rs) < 1e-9, (
                f"score diverged for {q!r} doc={pid}: py={ps} rs={rs}"
            )


def test_rust_reads_python_json(tmp_path: Path) -> None:
    """An index written by _Bm25Index must be loadable by RustBM25 and
    produce the same top-k."""
    RustBM25 = _get_rust_cls()

    path = tmp_path / "shared.json"
    py_idx = _Bm25Index(path)
    py_idx.build_index(_make_docs(FIXED_CORPUS))
    py_idx.flush()

    rs_idx = RustBM25(str(path))
    rs_idx.load()
    assert rs_idx.is_loaded()

    for q in ["sphinx", "jump", "lazy"]:
        py_hits = py_idx.search(q, top_k=5)
        rs_hits = rs_idx.search(q, top_k=5)
        assert [d for d, _ in py_hits] == [d for d, _ in rs_hits]


def test_python_reads_rust_json(tmp_path: Path) -> None:
    """An index written by RustBM25 must be loadable by _Bm25Index."""
    RustBM25 = _get_rust_cls()

    path = tmp_path / "shared_rs.json"
    rs_idx = RustBM25(str(path))
    rs_idx.build_index(_make_docs(FIXED_CORPUS))
    rs_idx.flush()

    py_idx = _Bm25Index(path)
    py_idx.load()
    assert py_idx.is_loaded()

    for q in ["sphinx", "jump", "lazy"]:
        rs_hits = rs_idx.search(q, top_k=5)
        py_hits = py_idx.search(q, top_k=5)
        assert [d for d, _ in rs_hits] == [d for d, _ in py_hits]


def test_wrapper_set_persist_path(tmp_path: Path) -> None:
    from locallens.pipeline import bm25 as cli_bm25

    orig_path = cli_bm25._index.persist_path
    redirect = tmp_path / "nested" / "idx.json"
    try:
        cli_bm25._set_persist_path(redirect)
        # RustBM25 returns a str; _Bm25Index returns a Path. Normalize so
        # the test works against either backend.
        assert Path(cli_bm25._index.persist_path) == redirect
        cli_bm25.build_index([{"id": str(uuid.uuid4()), "chunk_text": "hello world"}])
        assert redirect.exists()
    finally:
        # Restore so a later test doesn't see the redirect.
        cli_bm25._set_persist_path(orig_path)
