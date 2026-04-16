"""Sentence-transformer wrapper with lazy loading."""

import contextlib
import io
import os
import warnings

from rich.console import Console

from locallens.config import EMBEDDING_MODEL

console = Console()

_model = None


def _load_model():
    """Load the sentence-transformer model on first use.

    Silences the verbose BertModel LOAD REPORT and tqdm progress bars that
    sentence-transformers prints to stderr/stdout on first load, so the CLI
    output stays clean.
    """
    global _model
    if _model is None:
        console.print("[dim]Loading embedding model (first run only)...[/dim]")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        with (
            warnings.catch_warnings(),
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            warnings.simplefilter("ignore")
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-encode a list of texts into embedding vectors."""
    model = _load_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return list(embeddings.tolist())  # type: ignore[union-attr]


def embed_query(text: str) -> list[float]:
    """Encode a single query string into an embedding vector."""
    model = _load_model()
    embedding = model.encode(text, show_progress_bar=False)
    return list(embedding.tolist())  # type: ignore[union-attr]
