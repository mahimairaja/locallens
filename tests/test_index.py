"""Integration tests for indexing and searching via the Qdrant HTTP backend."""

import hashlib
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import TEST_COLLECTION

UUID_NAMESPACE = uuid.UUID("d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a")


def _point_id(file_path: str, chunk_index: int) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"{file_path}:{chunk_index}"))


def _file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _index_file(client, embedder, file_path: Path, extractor_name: str, text: str):
    """Index a single file's text into the test collection."""
    from qdrant_client.models import PointStruct

    # Simple chunking — for test purposes, single chunk per file
    chunks = [text] if len(text) < 500 else [text[i:i + 500] for i in range(0, len(text), 450)]
    abs_path = str(file_path.resolve())
    fhash = _file_hash(file_path)
    now = datetime.now(timezone.utc).isoformat()

    embeddings = embedder.encode(chunks).tolist()
    points = [
        PointStruct(
            id=_point_id(abs_path, i),
            vector={"text": emb},
            payload={
                "file_path": abs_path,
                "file_name": file_path.name,
                "file_type": file_path.suffix.lower(),
                "chunk_index": i,
                "chunk_text": chunk,
                "file_hash": fhash,
                "indexed_at": now,
                "extractor": extractor_name,
                "page_number": None,
                "file_modified_at": datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            },
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]

    client.upsert(collection_name=TEST_COLLECTION, points=points)
    return len(points)


class TestIndex:
    """Test indexing files and verifying points exist in Qdrant."""

    def test_index_txt(self, qdrant_client, embedder, test_folder):
        fp = test_folder / "sample.txt"
        text = fp.read_text(encoding="utf-8")
        count = _index_file(qdrant_client, embedder, fp, "text", text)
        assert count >= 1

        # Verify points exist
        info = qdrant_client.get_collection(TEST_COLLECTION)
        assert info.points_count >= 1

    def test_index_csv(self, qdrant_client, embedder, test_folder):
        fp = test_folder / "data.csv"
        from locallens.extractors.spreadsheet import SpreadsheetExtractor

        ext = SpreadsheetExtractor()
        text = ext.extract(fp)
        assert "Alice" in text
        count = _index_file(qdrant_client, embedder, fp, "spreadsheet", text)
        assert count >= 1

    def test_index_py(self, qdrant_client, embedder, test_folder):
        fp = test_folder / "hello.py"
        from locallens.extractors.code import CodeExtractor

        ext = CodeExtractor()
        text = ext.extract(fp)
        assert "def greet" in text
        count = _index_file(qdrant_client, embedder, fp, "code", text)
        assert count >= 1

    def test_index_eml(self, qdrant_client, embedder, test_folder):
        fp = test_folder / "sample.eml"
        from locallens.extractors.email_ext import EmailExtractor

        ext = EmailExtractor()
        text = ext.extract(fp)
        assert "Meeting Tomorrow" in text
        assert "alice@example.com" in text
        count = _index_file(qdrant_client, embedder, fp, "email", text)
        assert count >= 1


class TestSearch:
    """Test searching for indexed content."""

    def test_semantic_search_known_phrase(self, qdrant_client, embedder):
        """Search for a known phrase and verify the correct file appears."""
        query = "offline semantic search tool"
        vector = embedder.encode(query).tolist()

        results = qdrant_client.query_points(
            collection_name=TEST_COLLECTION,
            query=vector,
            using="text",
            limit=3,
            with_payload=True,
        )

        assert len(results.points) > 0
        # The sample.txt file should be in the top results
        file_names = [p.payload.get("file_name", "") for p in results.points]
        assert "sample.txt" in file_names

    def test_search_csv_content(self, qdrant_client, embedder):
        """Search for CSV content and verify the correct file appears."""
        query = "Alice Portland score"
        vector = embedder.encode(query).tolist()

        results = qdrant_client.query_points(
            collection_name=TEST_COLLECTION,
            query=vector,
            using="text",
            limit=3,
            with_payload=True,
        )

        assert len(results.points) > 0
        file_names = [p.payload.get("file_name", "") for p in results.points]
        assert "data.csv" in file_names

    def test_search_email_content(self, qdrant_client, embedder):
        """Search for email content and verify the .eml file appears."""
        query = "meeting tomorrow project roadmap"
        vector = embedder.encode(query).tolist()

        results = qdrant_client.query_points(
            collection_name=TEST_COLLECTION,
            query=vector,
            using="text",
            limit=3,
            with_payload=True,
        )

        assert len(results.points) > 0
        file_names = [p.payload.get("file_name", "") for p in results.points]
        assert "sample.eml" in file_names


class TestDelete:
    """Test deleting a file's points from Qdrant."""

    def test_delete_by_file(self, qdrant_client, test_folder):
        """Delete points for a file and verify they're gone."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        fp = test_folder / "hello.py"
        abs_path = str(fp.resolve())

        # Verify points exist before delete
        result = qdrant_client.count(
            collection_name=TEST_COLLECTION,
            count_filter=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=abs_path))]
            ),
            exact=True,
        )
        assert result.count > 0

        # Delete
        qdrant_client.delete(
            collection_name=TEST_COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=abs_path))]
            ),
        )

        # Allow for eventual consistency
        time.sleep(0.5)

        # Verify gone
        result = qdrant_client.count(
            collection_name=TEST_COLLECTION,
            count_filter=Filter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=abs_path))]
            ),
            exact=True,
        )
        assert result.count == 0
