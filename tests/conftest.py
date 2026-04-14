"""Shared pytest fixtures for LocalLens integration tests.

All tests use a dedicated "locallens_test" Qdrant collection (via the Docker
Qdrant server at http://localhost:6333) so production data is never touched.
The collection is created at session start and destroyed at session end.
"""

import csv
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------
TEST_COLLECTION = "locallens_test"
QDRANT_URL = os.environ.get("QDRANT_TEST_URL", "http://localhost:6333")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qdrant_client():
    """Return a QdrantClient connected to the test Qdrant instance.

    Creates the test collection at the start of the session and deletes it at
    the end. Skips the entire session if Qdrant is not reachable.
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    client = QdrantClient(url=QDRANT_URL, check_compatibility=False)

    # Verify connectivity
    try:
        client.get_collections()
    except Exception:
        pytest.skip("Qdrant server not reachable at " + QDRANT_URL)

    # Create (or recreate) the test collection
    collections = [c.name for c in client.get_collections().collections]
    if TEST_COLLECTION in collections:
        client.delete_collection(TEST_COLLECTION)

    client.create_collection(
        collection_name=TEST_COLLECTION,
        vectors_config={
            "text": VectorParams(size=384, distance=Distance.COSINE),
        },
    )
    # Declare payload indexes matching production schema
    for field in ("file_hash", "file_path", "file_type"):
        try:
            from qdrant_client.models import PayloadSchemaType

            client.create_payload_index(
                collection_name=TEST_COLLECTION,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass

    yield client

    # Teardown — delete the test collection
    try:
        client.delete_collection(TEST_COLLECTION)
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_folder():
    """Create a temporary folder with sample files for indexing tests.

    Contains:
      - sample.txt          (plain text with a known phrase)
      - data.csv            (CSV with column headers)
      - hello.py            (Python source)
      - sample.eml          (RFC 5322 email)
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="locallens_test_"))

    # -- .txt --
    (tmpdir / "sample.txt").write_text(
        "The quick brown fox jumps over the lazy dog. "
        "LocalLens is a 100% offline semantic search tool.\n",
        encoding="utf-8",
    )

    # -- .csv --
    csv_path = tmpdir / "data.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "City", "Score"])
        writer.writerow(["Alice", "Portland", "95"])
        writer.writerow(["Bob", "Seattle", "88"])

    # -- .py --
    (tmpdir / "hello.py").write_text(
        "def greet(name: str) -> str:\n"
        '    """Return a greeting for the given name."""\n'
        '    return f"Hello, {name}!"\n',
        encoding="utf-8",
    )

    # -- .eml --
    (tmpdir / "sample.eml").write_text(
        "From: alice@example.com\r\n"
        "To: bob@example.com\r\n"
        "Subject: Meeting Tomorrow\r\n"
        "Date: Mon, 14 Apr 2026 09:00:00 +0000\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Hi Bob,\r\n"
        "\r\n"
        "Let's meet tomorrow at 10am to discuss the project roadmap.\r\n"
        "\r\n"
        "Best,\r\n"
        "Alice\r\n",
        encoding="utf-8",
    )

    yield tmpdir

    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="session")
def embedder():
    """Load the sentence-transformers model once per session."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model
