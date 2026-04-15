"""Qdrant Edge shard wrapper — embedded vector store for the CLI.

Uses `qdrant-edge-py`'s ``EdgeShard`` (not ``qdrant-client``'s legacy embedded
mode). Both packages speak the same schema, so a CLI shard and the Docker
Qdrant backend can share a collection via the optional sync patterns in
``locallens/sync.py``.

Module-level API is intentionally unchanged from the prior qdrant-client
implementation (``init``, ``upsert_batch``, ``search``, ``count``,
``get_file_count``, ``get_all_hashes``) so callers in ``indexer.py``,
``searcher.py``, ``rag.py``, and ``cli.py`` don't need to change. Edge's
``ScoredPoint`` exposes the same ``.id`` / ``.score`` / ``.payload`` attrs
as qdrant-client's, so iteration in the RAG path Just Works.
"""

from __future__ import annotations

import atexit
from typing import Any

from qdrant_edge import (
    CountRequest,
    Distance,
    EdgeConfig,
    EdgeOptimizersConfig,
    EdgeShard,
    EdgeVectorParams,
    FacetRequest,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    Point,
    Query,
    QueryRequest,
    ScrollRequest,
    UpdateOperation,
)

from locallens.config import QDRANT_PATH, VECTOR_NAME, VECTOR_SIZE

# Indexed payload fields — keyword index on each enables O(1) filtered
# count/search (the whole point of the Phase 2 migration).
_INDEXED_FIELDS: tuple[str, ...] = ("file_hash", "file_path", "file_type")

_shard: EdgeShard | None = None


def _build_config() -> EdgeConfig:
    """Build the EdgeConfig used when creating a fresh shard."""
    return EdgeConfig(
        vectors={
            VECTOR_NAME: EdgeVectorParams(
                size=VECTOR_SIZE,
                distance=Distance.Cosine,
            )
        },
        # Tuned for the LocalLens use case: small/medium personal corpora,
        # frequent re-indexes, single-user. Defaults would also work; these
        # just make vacuum a bit more eager so deletes don't linger.
        optimizers=EdgeOptimizersConfig(
            deleted_threshold=0.2,
            vacuum_min_vector_number=100,
            default_segment_number=2,
        ),
    )


def _declare_payload_indexes(shard: EdgeShard) -> None:
    """Create keyword payload indexes for dedup and filtered search.

    Idempotent — checks the existing schema and only creates missing indexes.
    """
    try:
        existing = set(shard.info().payload_schema.keys())
    except Exception:
        existing = set()

    for field in _INDEXED_FIELDS:
        if field in existing:
            continue
        shard.update(
            UpdateOperation.create_field_index(field, PayloadSchemaType.Keyword)
        )


def _get_shard() -> EdgeShard:
    """Return a singleton EdgeShard, loading from disk or creating fresh."""
    global _shard
    if _shard is not None:
        return _shard

    QDRANT_PATH.mkdir(parents=True, exist_ok=True)

    # If the directory already has Edge data, load it. Otherwise create fresh.
    has_data = any(QDRANT_PATH.iterdir())
    if has_data:
        try:
            _shard = EdgeShard.load(str(QDRANT_PATH))
        except Exception:
            # Legacy qdrant-client embedded files — unusable by Edge. Tell
            # the user to clear the directory so we don't clobber their data.
            raise RuntimeError(
                f"{QDRANT_PATH} contains data that Qdrant Edge can't load. "
                f"If you're upgrading from the old qdrant-client embedded "
                f"store, run: rm -rf {QDRANT_PATH} and re-index."
            )
    else:
        _shard = EdgeShard.create(str(QDRANT_PATH), _build_config())

    _declare_payload_indexes(_shard)
    return _shard


def _close_on_exit() -> None:
    """Flush, optimize, and close the shard on interpreter shutdown."""
    global _shard
    if _shard is None:
        return
    try:
        _shard.optimize()
    except Exception:
        pass
    try:
        _shard.close()
    except Exception:
        pass
    _shard = None


atexit.register(_close_on_exit)


# ============================================================================
# Public API — callers in indexer.py / searcher.py / rag.py / cli.py rely on
# these names and signatures.
# ============================================================================


def init() -> None:
    """Ensure the shard exists and payload indexes are declared."""
    _get_shard()


def upsert_batch(points: list[dict[str, Any]]) -> None:
    """Upsert points into the shard.

    Accepts a list of plain dicts with ``id``, ``vector``, ``payload`` keys —
    the indexer builds these. We wrap them in ``Point`` with the named vector
    here so call sites don't need to know about the Edge schema.
    """
    if not points:
        return
    shard = _get_shard()
    edge_points = [
        Point(id=p["id"], vector={VECTOR_NAME: p["vector"]}, payload=p["payload"])
        for p in points
    ]
    # EdgeShard handles batching internally; still chunk on very large inputs
    # to avoid single-call memory spikes on huge directories.
    BATCH = 500
    for i in range(0, len(edge_points), BATCH):
        shard.update(UpdateOperation.upsert_points(edge_points[i : i + BATCH]))


def search(
    vector: list[float],
    top_k: int,
    file_type: str | None = None,
    path_prefix: str | None = None,
) -> list:
    """Nearest-neighbor search with optional payload filters.

    Returns a ``list[ScoredPoint]`` where each point has ``.id``, ``.score``,
    and ``.payload`` — call sites iterate these directly.
    """
    shard = _get_shard()
    query_filter = _build_filter(file_type=file_type, path_prefix=path_prefix)
    return shard.query(
        QueryRequest(
            limit=top_k,
            query=Query.Nearest(vector, using=VECTOR_NAME),
            filter=query_filter,
            with_payload=True,
        )
    )


def has_hash(file_hash: str) -> bool:
    """O(1) check for whether a file with this content hash is already indexed.

    Relies on the keyword payload index declared on ``file_hash``.
    Replaces the old full-collection scroll dedup pre-pass.
    """
    shard = _get_shard()
    n = shard.count(
        CountRequest(
            exact=True,
            filter=Filter(
                must=[
                    FieldCondition(key="file_hash", match=MatchValue(value=file_hash))
                ]
            ),
        )
    )
    return n > 0


def delete_by_file(file_path: str) -> None:
    """Delete every chunk belonging to a given file path."""
    shard = _get_shard()
    shard.update(
        UpdateOperation.delete_points_by_filter(
            Filter(
                must=[
                    FieldCondition(key="file_path", match=MatchValue(value=file_path))
                ]
            )
        )
    )


def count() -> int:
    """Total number of points in the shard."""
    shard = _get_shard()
    return int(shard.info().points_count or 0)


def get_file_count() -> int:
    """Count distinct ``file_path`` values.

    Uses scroll with ``with_payload=["file_path"]`` rather than facet — facet
    returns top-N by frequency which would truncate on large collections.
    """
    shard = _get_shard()
    paths: set[str] = set()
    offset = None
    while True:
        points, next_offset = shard.scroll(
            ScrollRequest(
                limit=256,
                offset=offset,
                with_payload=True,
                with_vector=False,
            )
        )
        for point in points:
            if point.payload and "file_path" in point.payload:
                paths.add(point.payload["file_path"])
        if next_offset is None:
            break
        offset = next_offset
    return len(paths)


def facet_file_types(limit: int = 20) -> list[tuple[str, int]]:
    """Facet over ``file_type`` for the stats command.

    Returns a list of ``(value, count)`` tuples, sorted by count descending.
    Falls back to a scroll-based aggregation if the facet hits shape isn't
    a list of ``FacetHit`` objects (older qdrant-edge-py builds).
    """
    shard = _get_shard()
    try:
        response = shard.facet(FacetRequest(key="file_type", limit=limit, exact=True))
        hits = getattr(response, "hits", None)
        if isinstance(hits, list):
            # Each hit has `.value` and `.count` attrs per the Edge model.
            return [(h.value, int(h.count)) for h in hits]
    except Exception:
        pass
    # Fallback — Python-side aggregation via scroll.
    counts: dict[str, int] = {}
    offset = None
    while True:
        points, next_offset = shard.scroll(
            ScrollRequest(
                limit=256, offset=offset, with_payload=True, with_vector=False
            )
        )
        for point in points:
            if point.payload and "file_type" in point.payload:
                ft = point.payload["file_type"]
                counts[ft] = counts.get(ft, 0) + 1
        if next_offset is None:
            break
        offset = next_offset
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]


# ----------------------------------------------------------------------------
# Legacy helpers still called from older code paths — kept as thin wrappers.
# ----------------------------------------------------------------------------


def get_all_hashes() -> set[str]:
    """DEPRECATED — prefer ``has_hash(fhash)`` for per-file O(1) lookup.

    Still here in case something outside the indexer relies on it. Returns
    the full hash set; does a single scroll.
    """
    shard = _get_shard()
    hashes: set[str] = set()
    offset = None
    while True:
        points, next_offset = shard.scroll(
            ScrollRequest(
                limit=256, offset=offset, with_payload=True, with_vector=False
            )
        )
        for point in points:
            if point.payload and "file_hash" in point.payload:
                hashes.add(point.payload["file_hash"])
        if next_offset is None:
            break
        offset = next_offset
    return hashes


def _build_filter(
    file_type: str | None = None, path_prefix: str | None = None
) -> Filter | None:
    """Build a ``Filter`` from optional CLI args. Returns ``None`` when no
    constraints apply so the query stays unfiltered."""
    must: list = []
    if file_type:
        must.append(FieldCondition(key="file_type", match=MatchValue(value=file_type)))
    if path_prefix:
        # Edge supports MatchText for substring/prefix matching — keep it simple
        # with an exact file_path match for now. Full prefix support will need
        # MatchText or Text index on file_path; deferred.
        must.append(
            FieldCondition(key="file_path", match=MatchValue(value=path_prefix))
        )
    if not must:
        return None
    return Filter(must=must)


# ----------------------------------------------------------------------------
# Accessor for sync.py — lets the push-sync worker access the underlying
# shard without exposing the singleton globally.
# ----------------------------------------------------------------------------


def get_shard() -> EdgeShard:
    """Return the underlying ``EdgeShard`` (loads/creates it if needed)."""
    return _get_shard()
