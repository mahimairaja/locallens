"""CLI ↔ Qdrant server sync for LocalLens.

Implements three patterns from the Qdrant Edge docs:

1. ``push``          — dual-write: after indexing, send the same points to a
                       remote Qdrant server via ``qdrant-client.upsert``.
2. ``pull``          — download a full shard snapshot from the server and
                       unpack it into the local Edge directory.
3. ``pull_partial``  — snapshot_manifest + update_from_snapshot: only the
                       segments that have changed are transferred.

All three are gated by ``QDRANT_SYNC_URL`` being configured; otherwise
``locallens`` runs fully offline with no network behaviour.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import httpx

from locallens.config import (
    COLLECTION_NAME,
    QDRANT_PATH,
    QDRANT_SYNC_API_KEY,
    QDRANT_SYNC_URL,
    VECTOR_NAME,
    VECTOR_SIZE,
)

# Only imported lazily inside the functions that need them so the CLI stays
# usable without network at import time.


def _require_sync_url() -> str:
    if not QDRANT_SYNC_URL:
        raise RuntimeError(
            "QDRANT_SYNC_URL is not set. Export QDRANT_SYNC_URL=http://localhost:6333 "
            "(or point at your Qdrant server) to enable sync."
        )
    return QDRANT_SYNC_URL


def _headers() -> dict[str, str]:
    return {"api-key": QDRANT_SYNC_API_KEY} if QDRANT_SYNC_API_KEY else {}


def _make_server_client():
    """Build a ``qdrant_client.QdrantClient`` pointed at the sync server."""
    from qdrant_client import QdrantClient

    url = _require_sync_url()
    return QdrantClient(url=url, api_key=QDRANT_SYNC_API_KEY)


def _ensure_remote_collection(server_client) -> None:
    """Create the remote collection with the matching named-vector schema.

    Both the CLI Edge shard and the backend use named vector ``text`` so the
    schemas line up and points can move between them without translation.
    """
    from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

    collections = {c.name for c in server_client.get_collections().collections}
    if COLLECTION_NAME not in collections:
        server_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                VECTOR_NAME: VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            },
        )

    # Idempotent payload indexes — match the CLI shard's schema.
    for field in ("file_hash", "file_path", "file_type"):
        try:
            server_client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            # qdrant-client raises if the index already exists — that's fine.
            pass


# ----------------------------------------------------------------------------
# Push pattern — dual-write after indexing
# ----------------------------------------------------------------------------


def push(points: list[dict]) -> int:
    """Push a batch of indexed points to the remote Qdrant server.

    ``points`` is the same plain-dict shape that ``indexer.index_folder``
    passes to ``store.upsert_batch``: ``{id, vector, payload}``. We rewrap
    each as a ``qdrant_client.models.PointStruct`` with the named vector and
    upsert in batches of 100.

    Returns the total number of points pushed.
    """
    if not points:
        return 0

    from qdrant_client.models import PointStruct

    server_client = _make_server_client()
    _ensure_remote_collection(server_client)

    server_points = [
        PointStruct(
            id=p["id"],
            vector={VECTOR_NAME: p["vector"]},
            payload=p["payload"],
        )
        for p in points
    ]

    BATCH = 100
    for i in range(0, len(server_points), BATCH):
        server_client.upsert(
            collection_name=COLLECTION_NAME,
            points=server_points[i : i + BATCH],
        )
    return len(server_points)


# ----------------------------------------------------------------------------
# Pull patterns — full and partial snapshot restore
# ----------------------------------------------------------------------------


def _create_and_download_full_snapshot(url: str, dest: Path) -> None:
    """Ask the server to create a snapshot, then download it to ``dest``."""
    snapshot_url = f"{url}/collections/{COLLECTION_NAME}/snapshots"
    with httpx.Client(headers=_headers(), timeout=300.0) as client:
        response = client.post(snapshot_url)
        response.raise_for_status()
        snapshot_name = response.json()["result"]["name"]

        download_url = f"{url}/collections/{COLLECTION_NAME}/snapshots/{snapshot_name}"
        with client.stream("GET", download_url) as stream:
            stream.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in stream.iter_bytes(chunk_size=8192):
                    f.write(chunk)


def pull() -> None:
    """Download a fresh full snapshot from the server and replace the local shard.

    Wipes ``QDRANT_PATH`` first. Use ``pull_partial`` instead if you want to
    keep the local shard warm and only transfer changed segments.
    """
    from qdrant_edge import EdgeShard

    url = _require_sync_url()
    data_dir = QDRANT_PATH
    data_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=str(data_dir.parent)) as restore_dir:
        snapshot_path = Path(restore_dir) / "shard.snapshot"
        _create_and_download_full_snapshot(url, snapshot_path)

        # Wipe the existing shard directory and unpack the new snapshot.
        if data_dir.exists():
            shutil.rmtree(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        EdgeShard.unpack_snapshot(str(snapshot_path), str(data_dir))


def pull_partial() -> None:
    """Partial snapshot sync — fetch only the segments that have changed.

    Requires an existing local shard. Gets the local manifest via
    ``snapshot_manifest()``, sends it to the server's partial-snapshot
    endpoint, then applies the returned delta via ``update_from_snapshot``.
    """
    from locallens import store as st

    url = _require_sync_url()
    shard = st.get_shard()
    manifest = shard.snapshot_manifest()

    partial_url = (
        f"{url}/collections/{COLLECTION_NAME}/shards/0/snapshot/partial/create"
    )

    with tempfile.TemporaryDirectory(dir=str(QDRANT_PATH)) as temp_dir:
        partial_snapshot_path = Path(temp_dir) / "partial.snapshot"
        with httpx.Client(headers=_headers(), timeout=300.0) as client:
            response = client.post(partial_url, json=manifest)
            response.raise_for_status()
            with open(partial_snapshot_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

        shard.update_from_snapshot(str(partial_snapshot_path))
