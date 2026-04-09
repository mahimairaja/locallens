"""Semantic search against the Qdrant collection."""

from locallens.embedder import embed_query
from locallens import store


def search(query: str, top_k: int) -> list:
    """Embed the query and return top-k nearest neighbor results from Qdrant."""
    store.init()
    vector = embed_query(query)
    return store.search(vector, top_k)
