# MCP Tools Reference

LocalLens exposes 5 tools via the MCP protocol.

## locallens_search

Search indexed files by semantic meaning, keywords, or hybrid.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | _(required)_ | Search query |
| `top_k` | `integer` | `5` | Max results |
| `file_type` | `string \| null` | `null` | Filter by extension |
| `mode` | `string` | `"hybrid"` | `"semantic"`, `"keyword"`, or `"hybrid"` |

**Response:**

```json
[
  {
    "file_path": "/Users/me/project/auth.py",
    "file_name": "auth.py",
    "file_type": ".py",
    "chunk_text": "def authenticate_user(username, password)...",
    "chunk_index": 2,
    "score": 0.8742,
    "extractor": "code"
  }
]
```

## locallens_ask

Ask a question and get an answer with source citations. Requires Ollama.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `question` | `string` | _(required)_ | Question to ask |
| `top_k` | `integer` | `3` | Context chunks |

**Response:**

```json
{
  "answer": "The authentication module uses bcrypt for password hashing...",
  "sources": [
    {
      "file_path": "/Users/me/project/auth.py",
      "file_name": "auth.py",
      "file_type": ".py",
      "chunk_text": "...",
      "chunk_index": 2,
      "score": 0.8742,
      "extractor": "code"
    }
  ],
  "model": "qwen2.5:3b",
  "duration_seconds": 4.12
}
```

## locallens_index

Index a folder of files for semantic search.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `folder_path` | `string` | _(required)_ | Folder to index |
| `force` | `boolean` | `false` | Re-index all files |

**Response:**

```json
{
  "total_files": 15,
  "new_files": 3,
  "updated_files": 0,
  "skipped_files": 12,
  "total_chunks": 487,
  "duration_seconds": 2.1
}
```

## locallens_status

Get current status including indexed file count and health checks.

**Parameters:** None.

**Response:**

```json
{
  "stats": {
    "total_files": 42,
    "total_chunks": 1284,
    "file_types": { ".py": 320, ".md": 280 },
    "collection_name": "locallens",
    "data_dir": "/Users/me/.locallens"
  },
  "health": [
    { "name": "Qdrant Edge", "status": "ok", "message": "1284 points in shard" },
    { "name": "Ollama", "status": "ok", "message": "Running at http://localhost:11434" }
  ]
}
```

## locallens_files

List all indexed files.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `file_type` | `string \| null` | `null` | Filter by extension |

**Response:**

```json
[
  {
    "file_path": "/Users/me/project/main.py",
    "file_name": "main.py",
    "file_type": ".py",
    "chunk_count": 8,
    "indexed_at": "2024-12-15T10:30:00Z"
  }
]
```
