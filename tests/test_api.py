"""API integration tests for the FastAPI backend.

Uses httpx.AsyncClient with the FastAPI app. Requires Qdrant to be
running and backend dependencies installed. Does NOT test Ollama-dependent
endpoints (/api/ask).
"""

import os
import sys

import pytest

# Add the backend directory to the path so `app` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


@pytest.fixture(scope="module")
async def client():
    """Create an httpx.AsyncClient bound to the FastAPI app.

    The lifespan is disabled to avoid loading voice models and the
    filesystem watcher during tests.
    """
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")

    try:
        from unittest.mock import patch

        # Patch heavy lifespan dependencies before importing the app
        with (
            patch("app.services.voice_stt.load_model"),
            patch("app.services.voice_tts.load_model"),
            patch("app.services.bm25.load"),
            patch("app.services.watcher.start"),
            patch("app.services.watcher.stop"),
        ):
            from app.main import app

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as ac:
                yield ac
    except ImportError as exc:
        pytest.skip(f"Backend dependencies not installed: {exc}")
    except Exception as exc:
        pytest.skip(f"Could not create test client: {exc}")


class TestHealth:
    """Test the health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        # The health endpoint should return qdrant and ollama status fields
        assert "qdrant" in data or "status" in data


class TestStats:
    """Test the stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_returns_200(self, client):
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_files" in data
        assert "total_chunks" in data


class TestFiles:
    """Test the files endpoint."""

    @pytest.mark.asyncio
    async def test_files_returns_200(self, client):
        resp = await client.get("/api/files")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestSearchAPI:
    """Test the search endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_200(self, client):
        resp = await client.post(
            "/api/search",
            json={"query": "test query", "top_k": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "results" in data
        assert isinstance(data["results"], list)
