"""Integration tests for namespace isolation."""

import time
import uuid
from datetime import datetime, timezone

import pytest

UUID_NAMESPACE = uuid.UUID("d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a")

NS_A = "locallens_test_ns_a"
NS_B = "locallens_test_ns_b"


class TestNamespaceIsolation:
    """Index to namespace A, search namespace B, verify nothing is returned."""

    @pytest.fixture(autouse=True)
    def setup_namespaces(self, qdrant_client, embedder):
        """Create two test namespace collections and index data into NS_A only."""
        from qdrant_client.models import Distance, PointStruct, VectorParams

        # Create NS_A and NS_B
        for ns in (NS_A, NS_B):
            collections = [c.name for c in qdrant_client.get_collections().collections]
            if ns in collections:
                qdrant_client.delete_collection(ns)
            qdrant_client.create_collection(
                collection_name=ns,
                vectors_config={
                    "text": VectorParams(size=384, distance=Distance.COSINE),
                },
            )

        # Index one point into NS_A
        text = "Namespace A contains important documents about quantum computing."
        embedding = embedder.encode(text).tolist()
        point_id = str(uuid.uuid5(UUID_NAMESPACE, "ns_a_doc:0"))
        qdrant_client.upsert(
            collection_name=NS_A,
            points=[
                PointStruct(
                    id=point_id,
                    vector={"text": embedding},
                    payload={
                        "file_path": "/tmp/ns_a_doc.txt",
                        "file_name": "ns_a_doc.txt",
                        "file_type": ".txt",
                        "chunk_index": 0,
                        "chunk_text": text,
                        "file_hash": "abc123",
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ],
        )

        yield

        # Teardown
        for ns in (NS_A, NS_B):
            try:
                qdrant_client.delete_collection(ns)
            except Exception:
                pass

    def test_ns_a_has_data(self, qdrant_client):
        """Namespace A should have the indexed point."""
        info = qdrant_client.get_collection(NS_A)
        assert info.points_count >= 1

    def test_ns_b_is_empty(self, qdrant_client):
        """Namespace B should have zero points."""
        info = qdrant_client.get_collection(NS_B)
        assert info.points_count == 0

    def test_search_ns_b_returns_nothing(self, qdrant_client, embedder):
        """Searching namespace B for content only in NS_A returns no results."""
        query = "quantum computing documents"
        vector = embedder.encode(query).tolist()

        results = qdrant_client.query_points(
            collection_name=NS_B,
            query=vector,
            using="text",
            limit=5,
            with_payload=True,
        )

        assert len(results.points) == 0

    def test_search_ns_a_returns_result(self, qdrant_client, embedder):
        """Searching namespace A should find the indexed document."""
        query = "quantum computing documents"
        vector = embedder.encode(query).tolist()

        results = qdrant_client.query_points(
            collection_name=NS_A,
            query=vector,
            using="text",
            limit=5,
            with_payload=True,
        )

        assert len(results.points) >= 1
        assert results.points[0].payload.get("file_name") == "ns_a_doc.txt"
