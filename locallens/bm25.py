"""BM25 keyword index for hybrid search (CLI side).

Maintains an in-memory BM25 index persisted at ~/.locallens/bm25_index.json.
"""

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

_BM25_PATH = Path.home() / ".locallens" / "bm25_index.json"

_bm25: BM25Okapi | None = None
_doc_ids: list[str] = []
_corpus_texts: list[str] = []


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def build_index(documents: list[dict]) -> None:
    global _bm25, _doc_ids, _corpus_texts
    _doc_ids = [str(d["id"]) for d in documents]
    _corpus_texts = [d.get("chunk_text", "") for d in documents]
    tokenized = [_tokenize(t) for t in _corpus_texts]
    _bm25 = BM25Okapi(tokenized) if tokenized else None
    _save()


def add_documents(documents: list[dict]) -> None:
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
    global _bm25, _doc_ids, _corpus_texts
    id_set = set(doc_ids)
    pairs = [
        (did, txt) for did, txt in zip(_doc_ids, _corpus_texts) if did not in id_set
    ]
    if pairs:
        _doc_ids, _corpus_texts = map(list, zip(*pairs))
    else:
        _doc_ids, _corpus_texts = [], []
    tokenized = [_tokenize(t) for t in _corpus_texts]
    _bm25 = BM25Okapi(tokenized) if tokenized else None
    _save()


def search(query: str, top_k: int = 10) -> list[tuple[str, float]]:
    if _bm25 is None or not _doc_ids:
        return []
    tokens = _tokenize(query)
    if not tokens:
        return []
    scores = _bm25.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return [(_doc_ids[idx], float(score)) for idx, score in ranked[:top_k] if score > 0]


def load() -> None:
    global _bm25, _doc_ids, _corpus_texts
    if not _BM25_PATH.exists():
        return
    try:
        data = json.loads(_BM25_PATH.read_text())
        _doc_ids = data.get("doc_ids", [])
        _corpus_texts = data.get("corpus_texts", [])
        tokenized = [_tokenize(t) for t in _corpus_texts]
        _bm25 = BM25Okapi(tokenized) if tokenized else None
    except Exception:
        pass


def _save() -> None:
    _BM25_PATH.parent.mkdir(parents=True, exist_ok=True)
    _BM25_PATH.write_text(
        json.dumps({"doc_ids": _doc_ids, "corpus_texts": _corpus_texts})
    )


def is_loaded() -> bool:
    return _bm25 is not None and len(_doc_ids) > 0
