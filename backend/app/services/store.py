"""Qdrant client wrapper for the FastAPI backend (HTTP mode)."""

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Return a singleton Qdrant client connected via HTTP."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def ensure_collection() -> None:
    """Create the collection if it does not already exist."""
    client = _get_client()
    collections = [c.name for c in client.get_collections().collections]
    if settings.collection_name not in collections:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(
                size=settings.vector_size,
                distance=Distance.COSINE,
            ),
        )


def upsert_chunks(points: list[PointStruct]) -> None:
    """Upsert points into the collection in batches of 100."""
    client = _get_client()
    ensure_collection()
    for i in range(0, len(points), 100):
        client.upsert(
            collection_name=settings.collection_name,
            points=points[i : i + 100],
        )


def search(vector: list[float], top_k: int) -> list:
    """Search the collection for nearest neighbors."""
    client = _get_client()
    ensure_collection()
    response = client.query_points(
        collection_name=settings.collection_name,
        query=vector,
        limit=top_k,
        with_payload=True,
    )
    return response.points


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
    """Return collection metadata including points count."""
    client = _get_client()
    ensure_collection()
    info = client.get_collection(settings.collection_name)
    return {
        "points_count": info.points_count,
        "vectors_count": info.vectors_count,
        "status": str(info.status),
    }


def get_all_hashes() -> set[str]:
    """Scroll through all points and collect unique file_hash values."""
    points = scroll_all()
    hashes: set[str] = set()
    for point in points:
        if point.payload and "file_hash" in point.payload:
            hashes.add(point.payload["file_hash"])
    return hashes
