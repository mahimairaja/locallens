"""BM25 keyword index for hybrid search.

Maintains an in-memory BM25 index alongside the Qdrant vector index.
The corpus is persisted as JSON so it survives restarts.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

_BM25_PATH = Path("data/bm25_index.json")

_bm25: Optional[BM25Okapi] = None
_doc_ids: list[str] = []
_corpus_texts: list[str] = []


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"\w+", text.lower())


def build_index(documents: list[dict]) -> None:
    """Build BM25 index from documents.

    Each document should have 'id' and 'chunk_text' keys.
    """
    global _bm25, _doc_ids, _corpus_texts

    _doc_ids = [str(d["id"]) for d in documents]
    _corpus_texts = [d.get("chunk_text", "") for d in documents]
    tokenized = [_tokenize(t) for t in _corpus_texts]

    _bm25 = BM25Okapi(tokenized) if tokenized else None

    _save()
    logger.info("BM25 index built with %d documents", len(_doc_ids))


def add_documents(documents: list[dict]) -> None:
    """Add documents to existing index (rebuilds)."""
    global _bm25, _doc_ids, _corpus_texts

    for d in documents:
        doc_id = str(d["id"])
        if doc_id in _doc_ids:
            idx = _doc_ids.index(doc_id)
            _corpus_texts[idx] = d.get("chunk_text", "")
        else:
            _doc_ids.append(doc_id)
            _corpus_texts.append(d.get("chunk_text", ""))

    tokenized = [_tokenize(t) for t in _corpus_texts]
    _bm25 = BM25Okapi(tokenized) if tokenized else None
    _save()


def remove_documents(doc_ids: list[str]) -> None:
    """Remove documents by ID and rebuild."""
    global _bm25, _doc_ids, _corpus_texts

    id_set = set(doc_ids)
    pairs = [(did, txt) for did, txt in zip(_doc_ids, _corpus_texts) if did not in id_set]
    if pairs:
        _doc_ids, _corpus_texts = map(list, zip(*pairs))
    else:
        _doc_ids, _corpus_texts = [], []

    tokenized = [_tokenize(t) for t in _corpus_texts]
    _bm25 = BM25Okapi(tokenized) if tokenized else None
    _save()


def search(query: str, top_k: int = 10) -> list[tuple[str, float]]:
    """Search BM25 index. Returns list of (doc_id, score) pairs."""
    if _bm25 is None or not _doc_ids:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    scores = _bm25.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in ranked[:top_k]:
        if score > 0:
            results.append((_doc_ids[idx], float(score)))
    return results


def load() -> None:
    """Load persisted BM25 index from disk."""
    global _bm25, _doc_ids, _corpus_texts

    if not _BM25_PATH.exists():
        return

    try:
        data = json.loads(_BM25_PATH.read_text())
        _doc_ids = data.get("doc_ids", [])
        _corpus_texts = data.get("corpus_texts", [])
        tokenized = [_tokenize(t) for t in _corpus_texts]
        _bm25 = BM25Okapi(tokenized) if tokenized else None
        logger.info("BM25 index loaded: %d documents", len(_doc_ids))
    except Exception as exc:
        logger.warning("Could not load BM25 index: %s", exc)


def _save() -> None:
    """Persist BM25 corpus to disk."""
    _BM25_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"doc_ids": _doc_ids, "corpus_texts": _corpus_texts}
    _BM25_PATH.write_text(json.dumps(data))


def is_loaded() -> bool:
    return _bm25 is not None and len(_doc_ids) > 0
