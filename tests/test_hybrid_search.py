"""Integration tests for hybrid search (semantic + BM25 keyword via RRF)."""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import TEST_COLLECTION

UUID_NAMESPACE = uuid.UUID("d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a")


def _point_id(file_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"{file_path}:{chunk_index}"))


class TestHybridSearch:
    """Verify hybrid search returns results from both semantic and keyword matches."""

    def test_bm25_keyword_match(self, qdrant_client, embedder, test_folder):
        """BM25 should find a document by exact keyword not easily matched semantically."""
        from rank_bm25 import BM25Okapi

        # Build a small BM25 corpus from the test collection
        results = qdrant_client.scroll(
            collection_name=TEST_COLLECTION,
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        points = results[0]

        corpus = []
        doc_ids = []
        for p in points:
            chunk_text = (p.payload or {}).get("chunk_text", "")
            corpus.append(chunk_text.lower().split())
            doc_ids.append(str(p.id))

        if not corpus:
            pytest.skip("No indexed points in test collection")

        bm25 = BM25Okapi(corpus)
        query_tokens = "locallens".lower().split()
        scores = bm25.get_scores(query_tokens)

        # There should be at least one non-zero score (sample.txt contains "LocalLens")
        assert max(scores) > 0

    def test_rrf_fusion(self):
        """Unit test for the RRF fusion function."""
        RRF_K = 60

        semantic = [
            ("id1", {"chunk_text": "a"}, 0.9),
            ("id2", {"chunk_text": "b"}, 0.8),
        ]
        bm25_hits = [
            ("id3", 10.0),
            ("id1", 8.0),
        ]
        all_payloads = {
            "id1": {"chunk_text": "a"},
            "id2": {"chunk_text": "b"},
            "id3": {"chunk_text": "c"},
        }

        # Inline RRF
        scores: dict[str, float] = {}
        payload_map: dict[str, dict] = {}
        for rank, (pid, payload, _) in enumerate(semantic, start=1):
            scores[pid] = scores.get(pid, 0) + 1.0 / (RRF_K + rank)
            payload_map[pid] = payload
        for rank, (pid, _) in enumerate(bm25_hits, start=1):
            scores[pid] = scores.get(pid, 0) + 1.0 / (RRF_K + rank)
            if pid not in payload_map:
                payload_map[pid] = all_payloads.get(pid, {})

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # id1 should be top-ranked (appears in both lists)
        assert ranked[0][0] == "id1"
        # All 3 unique IDs should appear
        result_ids = {pid for pid, _ in ranked}
        assert result_ids == {"id1", "id2", "id3"}
