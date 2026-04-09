"""Search service: embed query and search Qdrant for relevant chunks."""

import logging
import time

from app.models import SearchResponse, SearchResult
from app.services import embedder, store

logger = logging.getLogger(__name__)


def search(query: str, top_k: int = 10) -> SearchResponse:
    """Embed the query and return top-k nearest neighbor results from Qdrant.

    Args:
        query: The search query text.
        top_k: Maximum number of results to return.

    Returns:
        SearchResponse with ranked results and timing info.
    """
    store.ensure_collection()

    start = time.time()
    vector = embedder.encode_query(query)
    points = store.search(vector, top_k)
    elapsed_ms = round((time.time() - start) * 1000, 1)

    results: list[SearchResult] = []
    for rank, point in enumerate(points, start=1):
        payload = point.payload or {}
        results.append(
            SearchResult(
                rank=rank,
                score=round(float(point.score), 4),
                file_name=payload.get("file_name", ""),
                file_path=payload.get("file_path", ""),
                file_type=payload.get("file_type", ""),
                chunk_text=payload.get("chunk_text", ""),
                chunk_index=payload.get("chunk_index", 0),
            )
        )

    return SearchResponse(
        query=query,
        results=results,
        search_time_ms=elapsed_ms,
    )
