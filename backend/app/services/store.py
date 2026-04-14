"""Qdrant client wrapper for the FastAPI backend (HTTP mode).

Speaks the same named-vector schema as the CLI's Qdrant Edge shard
(``settings.vector_name``, default ``"text"``) so points sync cleanly
between the two. Declares payload indexes on ``file_hash``, ``file_path``,
``file_type`` for O(1) filtered search and dedup lookups.

All public functions accept an optional ``collection`` parameter so callers
can target a specific namespace collection.  When omitted the default
``settings.collection_name`` (``"locallens"``) is used.
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
    Range,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

_INDEXED_FIELDS: tuple[str, ...] = ("file_hash", "file_path", "file_type")

_client: QdrantClient | None = None
# Track which collections already have indexes declared this process.
_indexes_declared: set[str] = set()


def _get_client() -> QdrantClient:
    """Return a singleton Qdrant client connected via HTTP.

    ``check_compatibility=False`` disables the client<->server version
    warning -- our pinned server (Docker image v1.14.0) works fine with the
    newer 1.17+ client for every API we use.
    """
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
    return _client


def _col(collection: str | None) -> str:
    """Resolve *collection* to a concrete name, defaulting to ``settings.collection_name``."""
    return collection or settings.collection_name


def _declare_payload_indexes(client: QdrantClient, collection: str) -> None:
    """Create keyword payload indexes once per process per collection."""
    if collection in _indexes_declared:
        return
    for field in _INDEXED_FIELDS:
        try:
            client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            logger.debug("create_payload_index(%s, %s) skipped: %s", collection, field, exc)
    _indexes_declared.add(collection)


def ensure_collection(collection: str | None = None) -> None:
    """Create the collection with named vector + payload indexes.

    Named vector key is ``settings.vector_name`` (default ``"text"``). The
    CLI's Qdrant Edge shard uses the same key so points move between them
    without translation.
    """
    col = _col(collection)
    client = _get_client()
    collections = [c.name for c in client.get_collections().collections]
    if col not in collections:
        client.create_collection(
            collection_name=col,
            vectors_config={
                settings.vector_name: VectorParams(
                    size=settings.vector_size,
                    distance=Distance.COSINE,
                )
            },
        )
    _declare_payload_indexes(client, col)


def upsert_chunks(points: list[PointStruct], collection: str | None = None) -> None:
    """Upsert points into the collection in batches of 100."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    for i in range(0, len(points), 100):
        client.upsert(
            collection_name=col,
            points=points[i : i + 100],
        )


def search(
    vector: list[float],
    top_k: int,
    query_filter: Filter | None = None,
    collection: str | None = None,
) -> list:
    """Search the collection for nearest neighbours, optionally filtered."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    response = client.query_points(
        collection_name=col,
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
    date_from: str | None = None,
    date_to: str | None = None,
) -> Filter | None:
    """Build a Qdrant ``Filter`` from optional search-scope fields."""
    must: list[FieldCondition] = []
    if file_type:
        must.append(FieldCondition(key="file_type", match=MatchValue(value=file_type)))
    if path_prefix:
        must.append(FieldCondition(key="file_path", match=MatchValue(value=path_prefix)))
    if date_from or date_to:
        range_params = {}
        if date_from:
            range_params["gte"] = date_from
        if date_to:
            range_params["lte"] = date_to
        must.append(FieldCondition(key="file_modified_at", range=Range(**range_params)))
    if not must:
        return None
    return Filter(must=must)


def facet_file_types(limit: int = 20, collection: str | None = None) -> list[tuple[str, int]]:
    """Facet over ``file_type`` for the stats endpoint."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    try:
        response = client.facet(
            collection_name=col,
            key="file_type",
            limit=limit,
            exact=True,
        )
        return [(hit.value, int(hit.count)) for hit in response.hits]
    except Exception as exc:
        logger.debug("facet(file_type) failed, falling back to scroll: %s", exc)
        counts: dict[str, int] = {}
        for point in scroll_all(collection=col):
            ft = (point.payload or {}).get("file_type")
            if ft:
                counts[ft] = counts.get(ft, 0) + 1
        return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def scroll_all(collection: str | None = None) -> list:
    """Scroll through all points in the collection. Returns a flat list."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    all_points: list = []
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=col,
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


def delete_by_file(file_path: str, collection: str | None = None) -> None:
    """Delete all points whose payload file_path matches the given path."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    client.delete(
        collection_name=col,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="file_path",
                    match=MatchValue(value=file_path),
                )
            ]
        ),
    )


def get_collection_info(collection: str | None = None) -> dict:
    """Return collection metadata including points count and indexed payload fields."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    info = client.get_collection(col)
    return {
        "points_count": info.points_count or 0,
        "segments_count": info.segments_count or 0,
        "indexed_vectors_count": info.indexed_vectors_count or 0,
        "status": str(info.status),
        "payload_schema": list((info.payload_schema or {}).keys()),
    }


def get_points(ids: list[str], collection: str | None = None) -> list:
    """Retrieve points by their IDs."""
    col = _col(collection)
    client = _get_client()
    ensure_collection(col)
    try:
        return client.retrieve(
            collection_name=col,
            ids=ids,
            with_payload=True,
            with_vectors=False,
        )
    except Exception:
        return []


def get_all_hashes(collection: str | None = None) -> set[str]:
    """Scroll through all points and collect unique file_hash values."""
    points = scroll_all(collection=collection)
    hashes: set[str] = set()
    for point in points:
        if point.payload and "file_hash" in point.payload:
            hashes.add(point.payload["file_hash"])
    return hashes


def list_namespaces() -> list[str]:
    """Return all namespace names by scanning existing Qdrant collections.

    A collection is considered a LocalLens namespace if its name is
    ``"locallens"`` (mapped to the ``"default"`` namespace) or starts with
    ``"locallens_"``.
    """
    client = _get_client()
    namespaces: list[str] = []
    for c in client.get_collections().collections:
        if c.name == settings.collection_name:
            namespaces.append("default")
        elif c.name.startswith("locallens_"):
            namespaces.append(c.name[len("locallens_"):])
    # Always include "default" even if the collection hasn't been created yet.
    if "default" not in namespaces:
        namespaces.insert(0, "default")
    return sorted(namespaces)


def delete_collection(collection: str) -> None:
    """Delete a Qdrant collection entirely."""
    client = _get_client()
    try:
        client.delete_collection(collection_name=collection)
    except Exception as exc:
        logger.warning("delete_collection(%s) failed: %s", collection, exc)
    _indexes_declared.discard(collection)
