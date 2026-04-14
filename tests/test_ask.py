"""Integration test for the RAG ask flow.

Requires Ollama running with qwen2.5:3b pulled. Skips gracefully if not
available.
"""

import pytest
import httpx


class TestAsk:
    """Test the RAG ask pipeline via the backend."""

    def test_ask_returns_streamed_response(self, qdrant_client, embedder, test_folder):
        """Ask a question and verify a non-empty streamed response.

        This test uses the Ollama API directly (not through the backend) to
        avoid needing the full FastAPI server running. It builds a minimal
        context from the test collection and streams a response.
        """
        # Check Ollama is reachable
        try:
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code != 200:
                pytest.skip("Ollama not reachable")
        except Exception:
            pytest.skip("Ollama not reachable at localhost:11434")

        # Retrieve some context from the test collection
        query = "What tool does the document mention?"
        vector = embedder.encode(query).tolist()

        results = qdrant_client.query_points(
            collection_name="locallens_test",
            query=vector,
            using="text",
            limit=3,
            with_payload=True,
        )

        if not results.points:
            pytest.skip("No points in test collection — run index tests first")

        context_parts = []
        for p in results.points:
            fname = p.payload.get("file_name", "unknown")
            text = p.payload.get("chunk_text", "")
            context_parts.append(f"[File: {fname}]\n{text}")

        context = "\n---\n".join(context_parts)

        # Build prompt matching the production RAG prompt
        system_prompt = (
            "You are a helpful assistant answering questions about the user's local files. "
            "Answer ONLY based on the provided context. If the context doesn't contain "
            'the answer, say "I couldn\'t find relevant information in your indexed files."'
        )

        prompt = f"Context:\n{context}\n\nQuestion: {query}"

        # Stream response from Ollama
        response_text = ""
        try:
            with httpx.stream(
                "POST",
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:3b",
                    "system": system_prompt,
                    "prompt": prompt,
                    "stream": True,
                },
                timeout=30,
            ) as resp:
                for line in resp.iter_lines():
                    if line:
                        import json

                        data = json.loads(line)
                        token = data.get("response", "")
                        response_text += token
                        if data.get("done"):
                            break
        except Exception as exc:
            pytest.skip(f"Ollama streaming failed: {exc}")

        assert len(response_text.strip()) > 0, "RAG response was empty"
