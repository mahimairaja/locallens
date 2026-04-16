"""Sentence-transformer wrapper with lazy loading for the FastAPI backend."""

import contextlib
import io
import logging
import os
import warnings

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _load_model():
    """Load the sentence-transformer model on first use.

    Silences the verbose BertModel LOAD REPORT and tqdm progress bars that
    sentence-transformers prints on first load, keeping the backend logs clean.
    """
    global _model
    if _model is None:
        logger.info(
            "Loading embedding model '%s' (first use)...", settings.embedding_model
        )
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

            _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded.")
    return _model


def encode(texts: list[str]) -> list[list[float]]:
    """Batch-encode a list of texts into embedding vectors."""
    model = _load_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    return list(embeddings.tolist())  # type: ignore[union-attr]


def encode_query(text: str) -> list[float]:
    """Encode a single query string into an embedding vector."""
    model = _load_model()
    embedding = model.encode(text, show_progress_bar=False)
    return list(embedding.tolist())  # type: ignore[union-attr]
