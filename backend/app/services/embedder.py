"""Sentence-transformer wrapper with lazy loading for the FastAPI backend."""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Load the sentence-transformer model on first use."""
    global _model
    if _model is None:
        logger.info("Loading embedding model '%s' (first use)...", settings.embedding_model)
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded.")
    return _model


def encode(texts: list[str]) -> list[list[float]]:
    """Batch-encode a list of texts into embedding vectors."""
    model = _load_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def encode_query(text: str) -> list[float]:
    """Encode a single query string into an embedding vector."""
    model = _load_model()
    embedding = model.encode(text, show_progress_bar=False)
    return embedding.tolist()
