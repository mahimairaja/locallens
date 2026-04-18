# Data Classes

All public methods on `LocalLens` return one of these dataclasses. Each has a `to_dict()` method for JSON serialization.

```python
from locallens import IndexResult, SearchResult, AskResult, StatsResult, FileInfo, DoctorCheck
```

## IndexResult

Returned by `LocalLens.index()`.

| Field | Type | Description |
|---|---|---|
| `total_files` | `int` | Total files in index |
| `new_files` | `int` | Newly indexed files |
| `updated_files` | `int` | Re-indexed files |
| `skipped_files` | `int` | Skipped (unchanged) files |
| `total_chunks` | `int` | Total chunks in index |
| `duration_seconds` | `float` | Time taken |

```json
{
  "total_files": 42,
  "new_files": 5,
  "updated_files": 2,
  "skipped_files": 35,
  "total_chunks": 1284,
  "duration_seconds": 3.47
}
```

## SearchResult

Returned by `LocalLens.search()` (as a list).

| Field | Type | Description |
|---|---|---|
| `file_path` | `str` | Absolute path to the file |
| `file_name` | `str` | File name only |
| `file_type` | `str` | File extension (e.g. `.pdf`) |
| `chunk_text` | `str` | The matched text chunk |
| `chunk_index` | `int` | Chunk position within the file |
| `score` | `float` | Relevance score |
| `extractor` | `str \| None` | Extractor that produced this chunk |

```json
{
  "file_path": "/Users/me/Documents/report.pdf",
  "file_name": "report.pdf",
  "file_type": ".pdf",
  "chunk_text": "Q3 revenue exceeded projections by 12%...",
  "chunk_index": 3,
  "score": 0.8742,
  "extractor": "pymupdf"
}
```

## AskResult

Returned by `LocalLens.ask()`.

| Field | Type | Description |
|---|---|---|
| `answer` | `str` | The generated answer |
| `sources` | `list[SearchResult]` | Source chunks used for context |
| `model` | `str` | Ollama model used |
| `duration_seconds` | `float` | Time taken |

```json
{
  "answer": "Q3 revenue was $4.2M, exceeding projections by 12%.",
  "sources": [
    {
      "file_path": "/Users/me/Documents/report.pdf",
      "file_name": "report.pdf",
      "file_type": ".pdf",
      "chunk_text": "Q3 revenue exceeded projections...",
      "chunk_index": 3,
      "score": 0.8742,
      "extractor": "pymupdf"
    }
  ],
  "model": "qwen2.5:3b",
  "duration_seconds": 5.23
}
```

## AskStreamEvent

Yielded by `LocalLens.ask_stream()`.

| Field | Type | Description |
|---|---|---|
| `event_type` | `str` | `"token"` or `"sources"` |
| `data` | `Any` | Token string or list of SearchResult |

When `event_type` is `"token"`, `data` is a string (one token of the answer).
When `event_type` is `"sources"`, `data` is a `list[SearchResult]` with the context chunks.

## StatsResult

Returned by `LocalLens.stats()`.

| Field | Type | Description |
|---|---|---|
| `total_files` | `int` | Number of indexed files |
| `total_chunks` | `int` | Number of chunks |
| `file_types` | `dict[str, int]` | Chunk count per file type |
| `collection_name` | `str` | Qdrant collection name |
| `data_dir` | `str` | Data directory path |

```json
{
  "total_files": 42,
  "total_chunks": 1284,
  "file_types": {
    ".pdf": 450,
    ".py": 320,
    ".md": 280,
    ".txt": 234
  },
  "collection_name": "locallens",
  "data_dir": "/Users/me/.locallens"
}
```

## FileInfo

Returned by `LocalLens.files()` (as a list).

| Field | Type | Description |
|---|---|---|
| `file_path` | `str` | Absolute path |
| `file_name` | `str` | File name |
| `file_type` | `str` | File extension |
| `chunk_count` | `int` | Number of chunks |
| `indexed_at` | `str \| None` | ISO timestamp |

```json
{
  "file_path": "/Users/me/Documents/report.pdf",
  "file_name": "report.pdf",
  "file_type": ".pdf",
  "chunk_count": 15,
  "indexed_at": "2024-12-15T10:30:00Z"
}
```

## DoctorCheck

Returned by `LocalLens.doctor()` (as a list).

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Check name |
| `status` | `str` | `"ok"`, `"fail"`, or `"warn"` |
| `message` | `str` | Detail message |

```json
{
  "name": "Qdrant Edge",
  "status": "ok",
  "message": "1284 points in shard"
}
```
