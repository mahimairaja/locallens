"""Sentence-transformer wrapper with lazy loading."""

from rich.console import Console

from locallens.config import EMBEDDING_MODEL

console = Console()

_model = None


def _load_model():
    """Load the sentence-transformer model on first use."""
    global _model
    if _model is None:
        console.print("[dim]Loading embedding model (first run only)...[/dim]")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-encode a list of texts into embedding vectors."""
    model = _load_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """Encode a single query string into an embedding vector."""
    model = _load_model()
    embedding = model.encode(text, show_progress_bar=False)
    return embedding.tolist()
