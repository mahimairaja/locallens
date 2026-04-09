"""Qdrant client wrapper for embedded (local) mode."""

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from locallens.config import COLLECTION_NAME, QDRANT_PATH, VECTOR_SIZE

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Return a singleton Qdrant client, creating the storage directory if needed."""
    global _client
    if _client is None:
        QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=str(QDRANT_PATH))
    return _client


def init() -> None:
    """Create the collection if it does not already exist."""
    client = _get_client()
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def upsert_batch(points: list[PointStruct]) -> None:
    """Upsert points into the collection in batches of 100."""
    client = _get_client()
    init()
    for i in range(0, len(points), 100):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i : i + 100],
        )


def search(vector: list[float], top_k: int) -> list:
    """Search the collection for nearest neighbors."""
    client = _get_client()
    init()
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=top_k,
        with_payload=True,
    )
    return response.points


def get_all_hashes() -> set[str]:
    """Scroll through all points and collect unique file_hash values."""
    client = _get_client()
    init()
    hashes: set[str] = set()
    offset = None
    while True:
        result: ScrollResult = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = result
        for point in points:
            if point.payload and "file_hash" in point.payload:
                hashes.add(point.payload["file_hash"])
        if next_offset is None:
            break
        offset = next_offset
    return hashes


def count() -> int:
    """Return total number of points in the collection."""
    client = _get_client()
    init()
    info = client.get_collection(COLLECTION_NAME)
    return info.points_count


def get_file_count() -> int:
    """Count distinct file_path values by scrolling all points."""
    client = _get_client()
    init()
    paths: set[str] = set()
    offset = None
    while True:
        result: ScrollResult = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = result
        for point in points:
            if point.payload and "file_path" in point.payload:
                paths.add(point.payload["file_path"])
        if next_offset is None:
            break
        offset = next_offset
    return len(paths)
