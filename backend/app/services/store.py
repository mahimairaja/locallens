"""Qdrant client wrapper for the FastAPI backend (HTTP mode).

Speaks the same named-vector schema as the CLI's Qdrant Edge shard
(``settings.vector_name``, default ``"text"``) so points sync cleanly
between the two. Declares payload indexes on ``file_hash``, ``file_path``,
``file_type`` for O(1) filtered search and dedup lookups.
"""

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

_INDEXED_FIELDS: tuple[str, ...] = ("file_hash", "file_path", "file_type")

_client: QdrantClient | None = None
_indexes_declared: bool = False


def _get_client() -> QdrantClient:
    """Return a singleton Qdrant client connected via HTTP.

    ``check_compatibility=False`` disables the client↔server version
    warning — our pinned server (Docker image v1.14.0) works fine with the
    newer 1.17+ client for every API we use.
    """
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
    return _client


def _declare_payload_indexes(client: QdrantClient) -> None:
    """Create keyword payload indexes once per process.

    ``create_payload_index`` raises if the index already exists, so we guard
    with a process-local flag and swallow the "already exists" error to keep
    the call idempotent.
    """
    global _indexes_declared
    if _indexes_declared:
        return
    for field in _INDEXED_FIELDS:
        try:
            client.create_payload_index(
                collection_name=settings.collection_name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            # Index already exists — harmless on repeated startups.
            logger.debug("create_payload_index(%s) skipped: %s", field, exc)
    _indexes_declared = True


def ensure_collection() -> None:
    """Create the collection with named vector + payload indexes.

    Named vector key is ``settings.vector_name`` (default ``"text"``). The
    CLI's Qdrant Edge shard uses the same key so points move between them
    without translation.
    """
    client = _get_client()
    collections = [c.name for c in client.get_collections().collections]
    if settings.collection_name not in collections:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config={
                settings.vector_name: VectorParams(
                    size=settings.vector_size,
                    distance=Distance.COSINE,
                )
            },
        )
    _declare_payload_indexes(client)


def upsert_chunks(points: list[PointStruct]) -> None:
    """Upsert points into the collection in batches of 100."""
    client = _get_client()
    ensure_collection()
    for i in range(0, len(points), 100):
        client.upsert(
            collection_name=settings.collection_name,
            points=points[i : i + 100],
        )


def search(
    vector: list[float],
    top_k: int,
    query_filter: Filter | None = None,
) -> list:
    """Search the collection for nearest neighbours, optionally filtered.

    Uses ``using=settings.vector_name`` because the collection now stores
    points under a named vector. ``query_filter`` accepts any qdrant-client
    ``Filter``; callers typically build one from optional request fields
    in the searcher service.
    """
    client = _get_client()
    ensure_collection()
    response = client.query_points(
        collection_name=settings.collection_name,
        query=vector,
        using=settings.vector_name,
        limit=top_k,
        with_payload=True,
        query_filter=query_filter,
    )
    return response.points


def build_search_filter(
    file_type: str | None = None,
    path_prefix: str | None = None,
) -> Filter | None:
    """Build a Qdrant ``Filter`` from optional search-scope fields.

    Returns ``None`` when nothing was supplied so queries stay unfiltered.
    ``path_prefix`` is currently an exact ``file_path`` match — full prefix
    matching would need a text index on ``file_path``, deferred.
    """
    must: list[FieldCondition] = []
    if file_type:
        must.append(FieldCondition(key="file_type", match=MatchValue(value=file_type)))
    if path_prefix:
        must.append(FieldCondition(key="file_path", match=MatchValue(value=path_prefix)))
    if not must:
        return None
    return Filter(must=must)


def facet_file_types(limit: int = 20) -> list[tuple[str, int]]:
    """Facet over ``file_type`` for the stats endpoint.

    Uses ``client.facet`` (qdrant-client >= 1.13) against the payload index
    declared on ``file_type``. Falls back to a scroll-based aggregation if
    the server rejects the call for any reason (older server, missing
    index, etc.).
    """
    client = _get_client()
    ensure_collection()
    try:
        response = client.facet(
            collection_name=settings.collection_name,
            key="file_type",
            limit=limit,
            exact=True,
        )
        return [(hit.value, int(hit.count)) for hit in response.hits]
    except Exception as exc:
        logger.debug("facet(file_type) failed, falling back to scroll: %s", exc)
        counts: dict[str, int] = {}
        for point in scroll_all():
            ft = (point.payload or {}).get("file_type")
            if ft:
                counts[ft] = counts.get(ft, 0) + 1
        return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def scroll_all() -> list:
    """Scroll through all points in the collection. Returns a flat list."""
    client = _get_client()
    ensure_collection()
    all_points: list = []
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=settings.collection_name,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        all_points.extend(points)
        if next_offset is None:
            break
        offset = next_offset
    return all_points


def delete_by_file(file_path: str) -> None:
    """Delete all points whose payload file_path matches the given path."""
    client = _get_client()
    ensure_collection()
    client.delete(
        collection_name=settings.collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="file_path",
                    match=MatchValue(value=file_path),
                )
            ]
        ),
    )


def get_collection_info() -> dict:
    """Return collection metadata including points count and indexed payload fields."""
    client = _get_client()
    ensure_collection()
    info = client.get_collection(settings.collection_name)
    return {
        "points_count": info.points_count or 0,
        "segments_count": info.segments_count or 0,
        "indexed_vectors_count": info.indexed_vectors_count or 0,
        "status": str(info.status),
        "payload_schema": list((info.payload_schema or {}).keys()),
    }


def get_all_hashes() -> set[str]:
    """Scroll through all points and collect unique file_hash values."""
    points = scroll_all()
    hashes: set[str] = set()
    for point in points:
        if point.payload and "file_hash" in point.payload:
            hashes.add(point.payload["file_hash"])
    return hashes
