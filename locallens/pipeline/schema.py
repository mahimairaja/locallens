"""Schema versioning for Qdrant collections.

Tracks desired payload schema vs stored schema and performs additive
migrations (new payload indexes). Breaking changes (vector config)
refuse to start with a clear error.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

_SCHEMA_FILE = Path.home() / ".locallens" / "schema_versions.json"


@dataclass
class SchemaVersion:
    version: int
    payload_fields: dict[str, str]
    vector_config: dict[str, object]
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class CollectionSchema:
    name: str
    current: SchemaVersion
    history: list[SchemaVersion] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "current": self.current.to_dict(),
            "history": [v.to_dict() for v in self.history],
        }


def _load_all() -> dict[str, CollectionSchema]:
    if not _SCHEMA_FILE.exists():
        return {}
    try:
        raw = json.loads(_SCHEMA_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    result: dict[str, CollectionSchema] = {}
    for name, data in raw.items():
        current = SchemaVersion(**data["current"])
        history = [SchemaVersion(**v) for v in data.get("history", [])]
        result[name] = CollectionSchema(name=name, current=current, history=history)
    return result


def _save_all(schemas: dict[str, CollectionSchema]) -> None:
    _SCHEMA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: cs.to_dict() for name, cs in schemas.items()}
    tmp = _SCHEMA_FILE.with_suffix(".tmp")
    data = json.dumps(payload, indent=2, default=str)
    with open(tmp, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _SCHEMA_FILE)


def get_schema(collection_name: str) -> CollectionSchema | None:
    """Return the stored schema for a collection, or None."""
    schemas = _load_all()
    return schemas.get(collection_name)


def get_all_schemas() -> dict[str, CollectionSchema]:
    """Return all stored schemas."""
    return _load_all()


# ── desired schema (source of truth) ───────────────────────────────

DESIRED_PAYLOAD_FIELDS: dict[str, str] = {
    "file_path": "keyword",
    "file_name": "keyword",
    "file_type": "keyword",
    "chunk_text": "text",
    "chunk_index": "integer",
    "file_hash": "keyword",
    "indexed_at": "keyword",
}

DESIRED_VECTOR_CONFIG: dict[str, object] = {
    "name": "text",
    "size": 384,
    "distance": "Cosine",
}


def desired_schema(collection_name: str = "locallens") -> SchemaVersion:
    """Return the current desired schema."""
    return SchemaVersion(
        version=0,
        payload_fields=dict(DESIRED_PAYLOAD_FIELDS),
        vector_config=dict(DESIRED_VECTOR_CONFIG),
    )


# ── migration logic ────────────────────────────────────────────────


class SchemaBreakingChange(Exception):
    """Raised when a vector config change requires re-indexing."""


def check_and_migrate(collection_name: str = "locallens") -> SchemaVersion:
    """Compare desired schema against stored. Migrate if needed.

    Returns the current schema version after migration.

    Raises:
        SchemaBreakingChange: If vector config changed (requires re-index).
    """
    schemas = _load_all()
    desired = desired_schema(collection_name)
    now = datetime.now(UTC).isoformat()

    stored = schemas.get(collection_name)

    if stored is None:
        # New collection: store as version 1
        desired.version = 1
        desired.created_at = now
        schemas[collection_name] = CollectionSchema(
            name=collection_name,
            current=desired,
            history=[desired],
        )
        _save_all(schemas)
        log.info("Schema initialized: %s v1", collection_name)
        return desired

    current = stored.current

    # Check for breaking vector config changes
    if current.vector_config != desired.vector_config:
        raise SchemaBreakingChange(
            f"Vector config changed for '{collection_name}'. "
            f"Re-index required. Run: locallens index --force <folder>"
        )

    # Check for breaking changes: removed fields or type changes
    new_fields = set(desired.payload_fields) - set(current.payload_fields)
    removed_fields = set(current.payload_fields) - set(desired.payload_fields)
    common_fields = set(current.payload_fields) & set(desired.payload_fields)
    type_changes = [
        f
        for f in common_fields
        if current.payload_fields[f] != desired.payload_fields[f]
    ]

    if removed_fields or type_changes:
        details = []
        if removed_fields:
            details.append(f"removed fields: {sorted(removed_fields)}")
        if type_changes:
            details.append(f"type changes: {sorted(type_changes)}")
        raise SchemaBreakingChange(
            f"Schema breaking change for '{collection_name}': {', '.join(details)}. "
            f"Re-index required. Run: locallens index --force <folder>"
        )

    if not new_fields:
        return current

    new_version = current.version + 1

    log.info(
        "Schema migrated from v%d to v%d: added fields %s",
        current.version,
        new_version,
        list(new_fields),
    )

    updated = SchemaVersion(
        version=new_version,
        payload_fields=dict(desired.payload_fields),
        vector_config=dict(desired.vector_config),
        created_at=now,
    )
    stored.history.append(updated)
    stored.current = updated
    _save_all(schemas)
    return updated
