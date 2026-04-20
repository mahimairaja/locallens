"""Shared BM25 core — single source of truth for both the CLI and backend.

Both ``locallens/bm25.py`` and ``backend/app/services/bm25.py`` used to carry
near-identical copies of a ``rank_bm25``-based implementation that rebuilt the
entire BM25 index and rewrote the full JSON file on every ``add_documents``
call. For an indexer that calls ``add_documents`` once per file, this is
O(N^2) in the number of files and dominates wall-clock time (see
``bench-results/FINDINGS.md``).

This module replaces that with a parameterised ``_Bm25Index`` class that:

* maintains running ``df`` / ``total_tokens`` counters so ``add_documents``
  and ``remove_documents`` do only per-doc work;
* stores per-doc term-frequency dicts so scoring never retokenizes;
* recomputes ``idf`` lazily on first ``search`` after a mutation;
* defers persistence — writes are marked dirty and batched, with an
  ``atexit`` hook and an explicit ``flush()`` for graceful shutdown;
* keeps the on-disk JSON shape identical to the pre-fix format so existing
  indexes load without migration and downgrades remain safe.

Ranking semantics match ``rank_bm25.BM25Okapi`` exactly: same ``k1=1.5``,
``b=0.75``, epsilon-smoothed IDF (``epsilon=0.25``).

The module is private (leading underscore) — callers import the thin
wrappers in ``locallens/bm25.py`` and ``backend/app/services/bm25.py``.
"""

from __future__ import annotations

import atexit
import json
import logging
import math
import os
import re
import threading
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class _DocState:
    doc_ids: list[str] = field(default_factory=list)
    id_to_idx: dict[str, int] = field(default_factory=dict)
    doc_tf: list[dict[str, int]] = field(default_factory=list)  # per-doc term freq
    doc_lengths: list[int] = field(default_factory=list)
    corpus_texts: list[str] = field(default_factory=list)
    df: dict[str, int] = field(default_factory=dict)
    total_tokens: int = 0
    idf: dict[str, float] | None = None  # None == dirty, recompute on next search


class _Bm25Index:
    """Incremental BM25 Okapi index backed by a JSON file.

    Single-process, not thread-safe for concurrent writers. A module-level
    ``threading.Lock`` guards the flush path so the ``atexit`` hook and an
    explicit ``flush()`` call cannot produce an interleaved partial write.
    """

    def __init__(
        self,
        persist_path: Path,
        *,
        k1: float = 1.5,
        b: float = 0.75,
        epsilon: float = 0.25,
        logger: logging.Logger | None = None,
    ) -> None:
        self._persist_path = Path(persist_path)
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon
        self._log = logger
        self._state = _DocState()
        self._dirty = False
        self._atexit_registered = False
        self._save_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API (mirrors the old module-level functions)
    # ------------------------------------------------------------------

    def build_index(self, documents: list[dict]) -> None:
        """(Re)build the index from scratch. Eagerly persists."""
        self._state = _DocState()
        self._add_internal(documents)
        self._save_now()
        self._dirty = False
        if self._log is not None:
            self._log.info(
                "BM25 index built with %d documents", len(self._state.doc_ids)
            )

    def add_documents(self, documents: list[dict]) -> None:
        """Append or in-place update documents. Defers write by default."""
        if not documents:
            return
        self._add_internal(documents)
        self._mark_dirty()

    def remove_documents(self, doc_ids: list[str]) -> None:
        """Remove documents by id. Defers write by default.

        In-place decrement: subtract each removed doc's contribution from
        ``df`` and ``total_tokens`` directly, rather than rebuilding from
        the surviving docs. Cost is O(removed * avg_terms) for counters
        plus O(N_total) for the array compaction — strictly cheaper than
        the previous rebuild when removing a small number from a large
        corpus, and no worse otherwise.
        """
        if not doc_ids:
            return
        s = self._state
        id_set = set(doc_ids)
        drop_idx = [i for i, did in enumerate(s.doc_ids) if did in id_set]
        if not drop_idx:
            return

        # Subtract the removed docs' contributions to df / total_tokens.
        for i in drop_idx:
            s.total_tokens -= s.doc_lengths[i]
            for term in s.doc_tf[i]:
                c = s.df.get(term, 0) - 1
                if c <= 0:
                    s.df.pop(term, None)
                else:
                    s.df[term] = c

        # Compact the parallel arrays. Python lists don't support
        # mid-delete cheaply, so we rebuild the surviving slices in one
        # pass using a single set membership check.
        drop_set = set(drop_idx)
        s.doc_ids = [v for i, v in enumerate(s.doc_ids) if i not in drop_set]
        s.doc_tf = [v for i, v in enumerate(s.doc_tf) if i not in drop_set]
        s.doc_lengths = [v for i, v in enumerate(s.doc_lengths) if i not in drop_set]
        s.corpus_texts = [v for i, v in enumerate(s.corpus_texts) if i not in drop_set]
        s.id_to_idx = {did: i for i, did in enumerate(s.doc_ids)}
        s.idf = None
        self._mark_dirty()

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        s = self._state
        if not s.doc_ids:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []

        if s.idf is None:
            self._recompute_idf()
        assert s.idf is not None
        idf = s.idf
        N = len(s.doc_ids)  # > 0 — checked above via ``if not s.doc_ids``
        avgdl = s.total_tokens / N
        k1 = self.k1
        b = self.b

        scores = [0.0] * N
        # Iterate query tokens — rank_bm25 sums per-token contributions, so a
        # repeated token in the query adds its contribution twice. We match
        # that behaviour exactly for parity.
        for qt in tokens:
            qidf = idf.get(qt, 0.0)
            if qidf == 0.0:
                continue
            for i in range(N):
                tf = s.doc_tf[i].get(qt)
                if not tf:
                    continue
                dl = s.doc_lengths[i]
                if avgdl > 0:
                    denom = tf + k1 * (1 - b + b * dl / avgdl)
                else:
                    denom = tf + k1
                scores[i] += qidf * (tf * (k1 + 1)) / denom

        ranked = sorted(
            ((i, sc) for i, sc in enumerate(scores) if sc > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(s.doc_ids[i], float(sc)) for i, sc in ranked[:top_k]]

    def load(self) -> None:
        """Load persisted index. Tolerates old-format JSON without migration."""
        if not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text())
        except Exception as exc:
            if self._log is not None:
                self._log.warning("Could not load BM25 index: %s", exc)
            return

        doc_ids = [str(x) for x in data.get("doc_ids", [])]
        corpus_texts = [str(x) for x in data.get("corpus_texts", [])]
        if len(doc_ids) != len(corpus_texts):
            if self._log is not None:
                self._log.warning(
                    "BM25 index on disk is inconsistent (doc_ids=%d, corpus_texts=%d); "
                    "ignoring.",
                    len(doc_ids),
                    len(corpus_texts),
                )
            return

        state = _DocState()
        for did, txt in zip(doc_ids, corpus_texts):
            tokens = _tokenize(txt)
            tf = Counter(tokens)
            state.doc_ids.append(did)
            state.id_to_idx[did] = len(state.doc_ids) - 1
            state.doc_tf.append(dict(tf))
            state.doc_lengths.append(len(tokens))
            state.corpus_texts.append(txt)
            state.total_tokens += len(tokens)
            for term in tf:
                state.df[term] = state.df.get(term, 0) + 1

        self._state = state
        self._dirty = False  # just loaded; disk matches memory
        if self._log is not None:
            self._log.info("BM25 index loaded: %d documents", len(state.doc_ids))

    def is_loaded(self) -> bool:
        return len(self._state.doc_ids) > 0

    def flush(self) -> None:
        """Persist pending changes. Idempotent; safe to call multiple times."""
        if not self._dirty:
            return
        self._save_now()
        self._dirty = False

    # ------------------------------------------------------------------
    # Helpers used by wrapper modules and the bench harness
    # ------------------------------------------------------------------

    def set_persist_path(self, path: Path) -> None:
        """Change the on-disk location. Flushes pending writes to the old path
        first so nothing is lost. Used by tests and the bench harness."""
        self.flush()
        self._persist_path = Path(path)

    @property
    def persist_path(self) -> Path:
        return self._persist_path

    @property
    def state(self) -> _DocState:
        """Expose internal state for tests. Do not mutate from outside."""
        return self._state

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _add_internal(self, documents: Iterable[dict]) -> None:
        s = self._state
        for d in documents:
            doc_id = str(d["id"])
            text = d.get("chunk_text", "") or ""
            tokens = _tokenize(text)
            tf = dict(Counter(tokens))
            length = len(tokens)

            existing_idx = s.id_to_idx.get(doc_id)
            if existing_idx is not None:
                # Subtract the old contribution before writing the new one.
                old_tf = s.doc_tf[existing_idx]
                s.total_tokens -= s.doc_lengths[existing_idx]
                for term in old_tf:
                    c = s.df.get(term, 0) - 1
                    if c <= 0:
                        s.df.pop(term, None)
                    else:
                        s.df[term] = c
                s.doc_tf[existing_idx] = tf
                s.doc_lengths[existing_idx] = length
                s.corpus_texts[existing_idx] = text
            else:
                s.id_to_idx[doc_id] = len(s.doc_ids)
                s.doc_ids.append(doc_id)
                s.doc_tf.append(tf)
                s.doc_lengths.append(length)
                s.corpus_texts.append(text)

            s.total_tokens += length
            for term in tf:
                s.df[term] = s.df.get(term, 0) + 1

        s.idf = None  # mark dirty

    def _recompute_idf(self) -> None:
        s = self._state
        N = len(s.doc_ids)
        if N == 0:
            s.idf = {}
            return
        # rank_bm25 BM25Okapi formula, with epsilon smoothing.
        raw: dict[str, float] = {}
        neg_terms: list[str] = []
        idf_sum = 0.0
        for term, df_t in s.df.items():
            val = math.log((N - df_t + 0.5) / (df_t + 0.5))
            raw[term] = val
            idf_sum += val
            if val < 0:
                neg_terms.append(term)
        avg_idf = idf_sum / len(raw) if raw else 0.0
        floor = self.epsilon * avg_idf
        for term in neg_terms:
            raw[term] = floor
        s.idf = raw

    def _mark_dirty(self) -> None:
        self._dirty = True
        if _eager_flush_env():
            self._save_now()
            self._dirty = False
            return
        if not self._atexit_registered:
            atexit.register(self.flush)
            self._atexit_registered = True

    def _save_now(self) -> None:
        s = self._state
        with self._save_lock:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._persist_path.with_suffix(self._persist_path.suffix + ".tmp")
            payload = {"doc_ids": s.doc_ids, "corpus_texts": s.corpus_texts}
            tmp.write_text(json.dumps(payload))
            os.replace(tmp, self._persist_path)


def _eager_flush_env() -> bool:
    """Env escape hatch for debugging — persist on every mutation."""
    val = os.environ.get("LOCALLENS_BM25_EAGER_FLUSH", "").strip().lower()
    return val in ("1", "true", "yes", "on")
