"""Search service: semantic, keyword (BM25), and hybrid (RRF) modes."""

import logging
import time

from app.models import SearchResponse, SearchResult
from app.services import bm25, embedder, store

logger = logging.getLogger(__name__)

RRF_K = 60


def _rrf_fuse(
    semantic_results: list[tuple[str, dict, float]],
    bm25_results: list[tuple[str, float]],
    all_payloads: dict[str, dict],
    top_k: int,
) -> list[tuple[str, dict, float]]:
    """Reciprocal Rank Fusion with k=60."""
    scores: dict[str, float] = {}
    payload_map: dict[str, dict] = {}

    # Semantic ranks
    for rank, (pid, payload, _score) in enumerate(semantic_results, start=1):
        scores[pid] = scores.get(pid, 0) + 1.0 / (RRF_K + rank)
        payload_map[pid] = payload

    # BM25 ranks
    for rank, (pid, _score) in enumerate(bm25_results, start=1):
        scores[pid] = scores.get(pid, 0) + 1.0 / (RRF_K + rank)
        if pid not in payload_map:
            payload_map[pid] = all_payloads.get(pid, {})

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(pid, payload_map.get(pid, {}), score) for pid, score in ranked[:top_k]]


def search(
    query: str,
    top_k: int = 10,
    file_type: str | None = None,
    path_prefix: str | None = None,
    mode: str = "hybrid",
    date_from: str | None = None,
    date_to: str | None = None,
    collection: str | None = None,
) -> SearchResponse:
    """Search with semantic, keyword, or hybrid mode.

    Args:
        query: The search query text.
        top_k: Maximum number of results.
        file_type: Optional file_type filter.
        path_prefix: Optional path filter.
        mode: "semantic", "keyword", or "hybrid" (default).
        date_from: Optional ISO date string for range filter start.
        date_to: Optional ISO date string for range filter end.
        collection: Optional Qdrant collection name (namespace).
    """
    store.ensure_collection(collection)

    start = time.time()
    results: list[SearchResult] = []

    if mode == "keyword":
        results = _keyword_search(query, top_k, file_type, collection=collection)
    elif mode == "semantic":
        results = _semantic_search(
            query,
            top_k,
            file_type,
            path_prefix,
            date_from,
            date_to,
            collection=collection,
        )
    else:
        # Hybrid: combine semantic + keyword via RRF
        semantic = _semantic_search_raw(
            query,
            top_k * 2,
            file_type,
            path_prefix,
            date_from,
            date_to,
            collection=collection,
        )
        bm25_hits = bm25.search(query, top_k * 2)

        if not bm25_hits:
            # Fall back to pure semantic if BM25 index is empty
            results = _format_semantic(semantic, top_k)
        else:
            # Get payloads for BM25 hits that aren't in semantic results
            all_payloads = {pid: payload for pid, payload, _ in semantic}
            fused = _rrf_fuse(semantic, bm25_hits, all_payloads, top_k)
            results = [
                _make_result(rank, pid, payload, score)
                for rank, (pid, payload, score) in enumerate(fused, start=1)
                if payload
            ]

    elapsed_ms = round((time.time() - start) * 1000, 1)
    return SearchResponse(query=query, results=results, search_time_ms=elapsed_ms)


def _semantic_search_raw(
    query: str,
    top_k: int,
    file_type,
    path_prefix,
    date_from,
    date_to,
    collection: str | None = None,
) -> list[tuple[str, dict, float]]:
    """Raw semantic search returning (point_id, payload, score) tuples."""
    vector = embedder.encode_query(query)
    query_filter = store.build_search_filter(
        file_type=file_type,
        path_prefix=path_prefix,
        date_from=date_from,
        date_to=date_to,
    )
    points = store.search(
        vector, top_k, query_filter=query_filter, collection=collection
    )
    return [(str(p.id), p.payload or {}, float(p.score)) for p in points]


def _semantic_search(
    query, top_k, file_type, path_prefix, date_from, date_to, collection=None
) -> list[SearchResult]:
    raw = _semantic_search_raw(
        query, top_k, file_type, path_prefix, date_from, date_to, collection=collection
    )
    return _format_semantic(raw, top_k)


def _format_semantic(
    raw: list[tuple[str, dict, float]], top_k: int
) -> list[SearchResult]:
    results = []
    for rank, (pid, payload, score) in enumerate(raw[:top_k], start=1):
        results.append(_make_result(rank, pid, payload, score))
    return results


def _keyword_search(
    query: str, top_k: int, file_type: str | None, collection: str | None = None
) -> list[SearchResult]:
    """Pure BM25 keyword search."""
    hits = bm25.search(query, top_k * 2)
    results = []
    for rank, (doc_id, score) in enumerate(hits[:top_k], start=1):
        # Retrieve payload from Qdrant
        points = store.get_points([doc_id], collection=collection)
        if points:
            payload = points[0].payload or {}
            if file_type and payload.get("file_type") != file_type:
                continue
            results.append(_make_result(rank, doc_id, payload, score))
    return results


def _make_result(rank: int, pid: str, payload: dict, score: float) -> SearchResult:
    return SearchResult(
        rank=rank,
        score=round(score, 4),
        file_name=payload.get("file_name", ""),
        file_path=payload.get("file_path", ""),
        file_type=payload.get("file_type", ""),
        chunk_text=payload.get("chunk_text", ""),
        chunk_index=payload.get("chunk_index", 0),
        extractor=payload.get("extractor"),
        page_number=payload.get("page_number"),
    )
