"""Unit tests for the refine_search path (CLI engine + backend).

These tests use mocked embedder + store so they don't need Qdrant.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def _mock_embed(text: str) -> list[float]:
    """Deterministic mock: hash text to a fixed unit vector."""
    rng = np.random.RandomState(abs(hash(text)) % (2**31))
    vec = rng.randn(384)
    return (vec / np.linalg.norm(vec)).tolist()


def _fake_hit(payload: dict, score: float = 0.9):
    h = MagicMock()
    h.payload = payload
    h.score = score
    h.id = payload.get("file_path", "id")
    return h


class TestEngineRefineSearch:
    """Exercise LocalLens.refine_search end-to-end without Qdrant."""

    def _build_lens(self, store_hits):
        from locallens import LocalLens

        lens = LocalLens.__new__(LocalLens)
        lens._path = None
        lens._collection_name = "test"
        lens._data_dir = "/tmp"
        lens._embedding_model = "test"
        lens._ollama_url = "http://localhost:11434"
        lens._ollama_model = "qwen2.5:3b"
        lens._store_initialized = True
        lens._embed_query_fn = _mock_embed
        lens._embed_texts_fn = lambda texts: [_mock_embed(t) for t in texts]

        # Mock store
        store_mod = MagicMock()
        store_mod.search = MagicMock(return_value=store_hits)
        lens._store_module = store_mod
        return lens

    def test_refine_search_with_boost(self):
        hit = _fake_hit(
            {
                "file_path": "/docs/a.md",
                "file_name": "a.md",
                "file_type": ".md",
                "chunk_text": "boost match",
                "chunk_index": 0,
            }
        )
        lens = self._build_lens([hit])
        results = lens.refine_search(
            "pricing", add_texts=["quarterly revenue"], top_k=5
        )
        assert len(results) == 1
        assert results[0].file_name == "a.md"
        # Store called with a 384-dim normalized vector
        call_args = lens._store_module.search.call_args
        vector = call_args.args[0]
        assert len(vector) == 384
        assert abs(sum(v * v for v in vector) ** 0.5 - 1.0) < 1e-6

    def test_refine_search_with_suppress(self):
        hit = _fake_hit(
            {
                "file_path": "/a.md",
                "file_name": "a.md",
                "file_type": ".md",
                "chunk_text": "t",
                "chunk_index": 0,
            }
        )
        lens = self._build_lens([hit])
        results = lens.refine_search(
            "pricing", subtract_texts=["internal draft"], top_k=5
        )
        assert len(results) == 1

    def test_refine_search_with_arithmetic_query(self):
        hit = _fake_hit(
            {
                "file_path": "/a.md",
                "file_name": "a.md",
                "file_type": ".md",
                "chunk_text": "t",
                "chunk_index": 0,
            }
        )
        lens = self._build_lens([hit])
        # Query with arithmetic operators should go through combine_query_vectors
        results = lens.refine_search("pricing -draft +recent", top_k=3)
        assert len(results) == 1

    def test_refine_search_empty_both(self):
        """No add/subtract -- still embeds base_query and searches."""
        hit = _fake_hit(
            {
                "file_path": "/a.md",
                "file_name": "a.md",
                "file_type": ".md",
                "chunk_text": "t",
                "chunk_index": 0,
            }
        )
        lens = self._build_lens([hit])
        results = lens.refine_search("pricing", top_k=3)
        assert len(results) == 1

    def test_refine_search_passes_filters_to_store(self):
        lens = self._build_lens([])
        lens.refine_search(
            "q", add_texts=["x"], file_type=".pdf", path_prefix="/a", top_k=5
        )
        kwargs = lens._store_module.search.call_args.kwargs
        assert kwargs["file_type"] == ".pdf"
        assert kwargs["path_prefix"] == "/a"


class TestBackendRefineSearch:
    """Exercise backend refine_search service function."""

    def test_refine_preserves_all_filters(self):
        """Regression test for Codex finding: path_prefix/date_from/date_to
        must reach build_search_filter, not just file_type."""
        # Import inside test so the backend module can be patched
        import sys

        # Skip gracefully if fastapi/backend deps aren't installed
        try:
            import app.services.searcher as searcher_mod
        except ImportError:
            try:
                sys.path.insert(0, "backend")
                import app.services.searcher as searcher_mod  # noqa: F811
            except ImportError:
                pytest.skip("backend app not importable")

        # Patch store, embedder and ensure_collection
        with (
            patch.object(searcher_mod, "store") as mock_store,
            patch.object(searcher_mod, "embedder") as mock_embedder,
        ):
            mock_embedder.encode_query = _mock_embed
            mock_store.ensure_collection = MagicMock()
            mock_store.build_search_filter = MagicMock(return_value=None)
            mock_store.search = MagicMock(return_value=[])

            searcher_mod.refine_search(
                base_query="pricing",
                add_texts=["x"],
                file_type=".pdf",
                path_prefix="/docs",
                date_from="2024-01-01",
                date_to="2024-12-31",
            )

            # All four filter args should be forwarded
            kwargs = mock_store.build_search_filter.call_args.kwargs
            assert kwargs["file_type"] == ".pdf"
            assert kwargs["path_prefix"] == "/docs"
            assert kwargs["date_from"] == "2024-01-01"
            assert kwargs["date_to"] == "2024-12-31"

    def test_refine_with_arithmetic_query(self):
        """refine_search with query arithmetic should use combined vectors."""
        import sys

        try:
            import app.services.searcher as searcher_mod
        except ImportError:
            try:
                sys.path.insert(0, "backend")
                import app.services.searcher as searcher_mod  # noqa: F811
            except ImportError:
                pytest.skip("backend app not importable")

        with (
            patch.object(searcher_mod, "store") as mock_store,
            patch.object(searcher_mod, "embedder") as mock_embedder,
        ):
            mock_embedder.encode_query = _mock_embed
            mock_store.ensure_collection = MagicMock()
            mock_store.build_search_filter = MagicMock(return_value=None)
            mock_store.search = MagicMock(return_value=[])

            resp = searcher_mod.refine_search(
                base_query="pricing +recent -draft",
                add_texts=None,
                subtract_texts=None,
            )
            assert resp.query == "pricing +recent -draft"
            assert resp.results == []
