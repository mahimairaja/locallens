"""Tests for the schema versioning module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from locallens.pipeline.schema import (
    CollectionSchema,
    SchemaBreakingChange,
    SchemaVersion,
    _load_all,
    _save_all,
    check_and_migrate,
    desired_schema,
    get_all_schemas,
    get_schema,
)


@pytest.fixture
def tmp_schema_file(tmp_path, monkeypatch):
    """Redirect _SCHEMA_FILE to a temp path for isolation."""
    import locallens.pipeline.schema as mod

    p = tmp_path / "schema_versions.json"
    monkeypatch.setattr(mod, "_SCHEMA_FILE", p)
    return p


def test_get_schema_returns_none_when_missing(tmp_schema_file):
    assert get_schema("nonexistent") is None


def test_get_all_schemas_empty(tmp_schema_file):
    assert get_all_schemas() == {}


def test_check_and_migrate_new_collection(tmp_schema_file):
    """A brand-new collection is initialized as v1."""
    v = check_and_migrate("new_coll")
    assert v.version == 1
    assert v.payload_fields == desired_schema().payload_fields
    assert tmp_schema_file.exists()

    stored = get_schema("new_coll")
    assert stored is not None
    assert stored.current.version == 1
    assert len(stored.history) == 1


def test_check_and_migrate_no_change_returns_current(tmp_schema_file):
    check_and_migrate("stable")
    v1 = get_schema("stable").current
    v2 = check_and_migrate("stable")
    assert v2.version == v1.version


def test_vector_config_change_raises_breaking(tmp_schema_file, monkeypatch):
    check_and_migrate("vecchange")

    # Simulate code side changing vector size
    import locallens.pipeline.schema as mod

    new_desired = {"name": "text", "size": 768, "distance": "Cosine"}
    monkeypatch.setattr(mod, "DESIRED_VECTOR_CONFIG", new_desired)

    with pytest.raises(SchemaBreakingChange, match="Vector config"):
        check_and_migrate("vecchange")


def test_removed_field_raises_breaking(tmp_schema_file, monkeypatch):
    check_and_migrate("removed")

    import locallens.pipeline.schema as mod

    # Simulate removing a field from desired schema
    shrunk = {k: v for k, v in mod.DESIRED_PAYLOAD_FIELDS.items() if k != "indexed_at"}
    monkeypatch.setattr(mod, "DESIRED_PAYLOAD_FIELDS", shrunk)

    with pytest.raises(SchemaBreakingChange, match="removed fields"):
        check_and_migrate("removed")


def test_field_type_change_raises_breaking(tmp_schema_file, monkeypatch):
    check_and_migrate("typechange")

    import locallens.pipeline.schema as mod

    changed = dict(mod.DESIRED_PAYLOAD_FIELDS)
    changed["chunk_index"] = "keyword"  # was "integer"
    monkeypatch.setattr(mod, "DESIRED_PAYLOAD_FIELDS", changed)

    with pytest.raises(SchemaBreakingChange, match="type changes"):
        check_and_migrate("typechange")


def test_added_field_migrates_version_up(tmp_schema_file, monkeypatch):
    check_and_migrate("grow")
    v1 = get_schema("grow").current
    assert v1.version == 1

    import locallens.pipeline.schema as mod

    expanded = dict(mod.DESIRED_PAYLOAD_FIELDS)
    expanded["tags"] = "keyword"
    monkeypatch.setattr(mod, "DESIRED_PAYLOAD_FIELDS", expanded)

    v2 = check_and_migrate("grow")
    assert v2.version == 2
    assert "tags" in v2.payload_fields

    stored = get_schema("grow")
    assert len(stored.history) == 2


def test_save_and_load_roundtrip(tmp_schema_file):
    v = SchemaVersion(
        version=3,
        payload_fields={"a": "keyword"},
        vector_config={"name": "text", "size": 384, "distance": "Cosine"},
        created_at="2024-01-01",
    )
    cs = CollectionSchema(name="rt", current=v, history=[v])
    _save_all({"rt": cs})

    loaded = _load_all()
    assert "rt" in loaded
    assert loaded["rt"].current.version == 3
    assert loaded["rt"].current.payload_fields == {"a": "keyword"}


def test_load_skips_corrupt_records(tmp_schema_file):
    """Malformed entries should be logged and skipped, not crash."""
    import json

    tmp_schema_file.write_text(
        json.dumps(
            {
                "good": {
                    "current": {
                        "version": 1,
                        "payload_fields": {"a": "keyword"},
                        "vector_config": {
                            "name": "text",
                            "size": 384,
                            "distance": "Cosine",
                        },
                        "created_at": "2024-01-01",
                    },
                    "history": [],
                },
                "bad": {"oops": "missing_current"},
                "also_bad": "not_a_dict",
            }
        )
    )
    loaded = _load_all()
    assert "good" in loaded
    assert "bad" not in loaded
    assert "also_bad" not in loaded


def test_load_returns_empty_on_invalid_json(tmp_schema_file):
    tmp_schema_file.write_text("this is not json {{{")
    assert _load_all() == {}


def test_save_is_atomic(tmp_schema_file):
    """_save_all writes to .tmp then renames -- no partial file on success."""
    v = SchemaVersion(version=1, payload_fields={}, vector_config={}, created_at="x")
    cs = CollectionSchema(name="a", current=v)
    _save_all({"a": cs})
    # Ensure no stale .tmp file after success
    if tmp_schema_file.suffix == ".json":
        alt = tmp_schema_file.with_suffix(".tmp")
        assert not alt.exists()
