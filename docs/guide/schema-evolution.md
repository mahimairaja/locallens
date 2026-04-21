# Schema Evolution

LocalLens tracks the Qdrant collection schema across versions so that additive changes (new payload fields) are applied automatically and breaking changes (vector config) produce a clear error.

## How it works

Schema versions are stored in `~/.locallens/schema_versions.json`. Each collection has its own entry tracking:

- **Version number** (incremented on each change)
- **Payload fields** (field name to type mapping)
- **Vector config** (name, size, distance)
- **Created timestamp**

## Automatic migration

On startup, LocalLens compares the desired schema (defined in code) against the stored schema:

| Change Type | Behavior |
|---|---|
| **New collection** | Stores current schema as v1 |
| **No change** | Nothing happens |
| **New payload fields** | Creates new indexes, increments version, logs migration |
| **Removed fields** | Refuses to start with error, requires re-index |
| **Field type changes** | Refuses to start with error, requires re-index |
| **Vector config change** | Refuses to start with error, requires re-index |

## CLI commands

### Show current schema

```bash
locallens schema show
```

```text
┌──────────────────────────────────────┐
│   Schema: locallens (v1)             │
├───────────────┬──────────────────────┤
│ Field         │ Type                 │
├───────────────┼──────────────────────┤
│ file_path     │ keyword              │
│ file_name     │ keyword              │
│ file_type     │ keyword              │
│ chunk_text    │ text                 │
│ chunk_index   │ integer              │
│ file_hash     │ keyword              │
│ indexed_at    │ keyword              │
└───────────────┴──────────────────────┘
```

### Show schema history

```bash
locallens schema history
```

```
┌─────────────────────────────────────┐
│   Schema History: locallens         │
├─────────┬────────┬──────────────────┤
│ Version │ Fields │ Created          │
├─────────┼────────┼──────────────────┤
│ 1       │ 7      │ 2024-12-15T10:00 │
│ 2       │ 8      │ 2024-12-20T14:30 │
└─────────┴────────┴──────────────────┘
```

## Doctor integration

`locallens doctor` shows the current schema version:

```text
│ Schema Version │   ✓    │ v1 (7 fields) │
```

## Breaking changes

If the vector config changes (different dimension or distance metric), or if payload fields are removed or their types change, LocalLens refuses to start:

```text
Error: Schema breaking change for 'locallens': removed fields: ['old_field'].
Re-index required. Run: locallens index --force <folder>
```

This prevents silent data corruption from mismatched embeddings.
