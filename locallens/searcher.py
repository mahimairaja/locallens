"""Semantic search against the Qdrant Edge shard."""

from locallens.embedder import embed_query
from locallens import store


def search(
    query: str,
    top_k: int,
    file_type: str | None = None,
    path_prefix: str | None = None,
) -> list:
    """Embed the query and return top-k nearest neighbour results.

    Optional ``file_type`` and ``path_prefix`` filters are enforced via
    payload-indexed keyword match on the shard.
    """
    store.init()
    vector = embed_query(query)
    return store.search(vector, top_k, file_type=file_type, path_prefix=path_prefix)
