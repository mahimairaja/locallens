# Python API

The `LocalLens` class is the main entry point for all operations.

```python
from locallens import LocalLens
```

## Constructor

```python
LocalLens(
    path: str | Path | None = None,
    collection_name: str = "locallens",
    data_dir: str | Path | None = None,
    embedding_model: str = "all-MiniLM-L6-v2",
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "qwen2.5:3b",
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `path` | `str \| Path \| None` | `None` | Folder to index and search. Can be set later via `index()`. |
| `collection_name` | `str` | `"locallens"` | Qdrant collection name |
| `data_dir` | `str \| Path \| None` | `~/.locallens` | Where to store the Qdrant Edge shard and BM25 index |
| `embedding_model` | `str` | `"all-MiniLM-L6-v2"` | Sentence-transformers model name |
| `ollama_url` | `str` | `"http://localhost:11434"` | Ollama server URL (for `ask()`) |
| `ollama_model` | `str` | `"qwen2.5:3b"` | Ollama model name (for `ask()`) |

## `index()`

Index files in the configured path.

```python
def index(
    self,
    force: bool = False,
    callback: Callable[[str, str, float], None] | None = None,
) -> IndexResult
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `force` | `bool` | `False` | Re-index all files regardless of content hash |
| `callback` | `Callable \| None` | `None` | Optional `callback(event_type, message, progress)` |

**Returns:** [`IndexResult`](/api/data-classes#indexresult)

```python
lens = LocalLens("~/Documents")
result = lens.index()
print(f"Indexed {result.total_files} files ({result.total_chunks} chunks) in {result.duration_seconds}s")
```

## `search()`

Search indexed files by semantic meaning, keywords, or hybrid.

```python
def search(
    self,
    query: str,
    top_k: int = 5,
    mode: str = "hybrid",
    file_type: str | None = None,
    path_prefix: str | None = None,
) -> list[SearchResult]
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `str` | _(required)_ | Search query text. Supports query arithmetic: use `+` to add concepts and `-` to subtract (e.g. `"pricing +recent -draft"`) |
| `top_k` | `int` | `5` | Maximum results to return |
| `mode` | `str` | `"hybrid"` | `"semantic"`, `"keyword"`, or `"hybrid"` |
| `file_type` | `str \| None` | `None` | Filter by extension (e.g. `".pdf"`) |
| `path_prefix` | `str \| None` | `None` | Filter by file path prefix |

**Returns:** `list[`[`SearchResult`](/api/data-classes#searchresult)`]`

```python
# Hybrid search (default)
results = lens.search("quarterly revenue")

# Semantic only
results = lens.search("quarterly revenue", mode="semantic")

# Filter by file type
results = lens.search("quarterly revenue", file_type=".pdf")
```

## `ask()`

Ask a question about indexed files using RAG.

```python
def ask(
    self,
    question: str,
    top_k: int = 3,
) -> AskResult
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `question` | `str` | _(required)_ | Natural language question |
| `top_k` | `int` | `3` | Number of context chunks to retrieve |

**Returns:** [`AskResult`](/api/data-classes#askresult)

**Raises:** [`OllamaUnavailableError`](/api/exceptions) when Ollama is not running.

```python
result = lens.ask("What was the Q3 revenue?")
print(result.answer)
print(f"Model: {result.model}, took {result.duration_seconds}s")
for source in result.sources:
    print(f"  Source: {source.file_name}")
```

## `ask_stream()`

Stream a RAG answer token by token.

```python
def ask_stream(
    self,
    question: str,
    top_k: int = 3,
) -> Generator[AskStreamEvent, None, None]
```

**Yields:** [`AskStreamEvent`](/api/data-classes#askstreamevent) with `event_type` of `"token"` (data=str) or `"sources"` (data=list[SearchResult]).

**Raises:** [`OllamaUnavailableError`](/api/exceptions) when Ollama is not running.

```python
for event in lens.ask_stream("What was the Q3 revenue?"):
    if event.event_type == "token":
        print(event.data, end="", flush=True)
    elif event.event_type == "sources":
        print(f"\n\nSources: {[s.file_name for s in event.data]}")
```

## `stats()`

Get collection statistics.

```python
def stats(self) -> StatsResult
```

**Returns:** [`StatsResult`](/api/data-classes#statsresult)

```python
stats = lens.stats()
print(f"{stats.total_files} files, {stats.total_chunks} chunks")
print(f"File types: {stats.file_types}")
```

## `files()`

List all indexed files.

```python
def files(self) -> list[FileInfo]
```

**Returns:** `list[`[`FileInfo`](/api/data-classes#fileinfo)`]`

```python
for f in lens.files():
    print(f"{f.file_name} ({f.file_type}) — {f.chunk_count} chunks")
```

## `refine_search()`

Refine a search by boosting or suppressing specific result texts. This is the programmatic equivalent of clicking +/- buttons on search results.

```python
def refine_search(
    self,
    base_query: str,
    add_texts: list[str] | None = None,
    subtract_texts: list[str] | None = None,
    top_k: int = 5,
    file_type: str | None = None,
    path_prefix: str | None = None,
) -> list[SearchResult]
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `base_query` | `str` | _(required)_ | The original search query (may include +/- arithmetic) |
| `add_texts` | `list[str] \| None` | `None` | Chunk texts to boost (add to query direction) |
| `subtract_texts` | `list[str] \| None` | `None` | Chunk texts to suppress (subtract from query direction) |
| `top_k` | `int` | `5` | Maximum results |
| `file_type` | `str \| None` | `None` | Filter by extension |
| `path_prefix` | `str \| None` | `None` | Filter by path prefix |

**Returns:** `list[`[`SearchResult`](/api/data-classes#searchresult)`]`

```python
# First search
results = lens.search("pricing strategy")

# Boost results like the first hit, suppress results like the third
refined = lens.refine_search(
    "pricing strategy",
    add_texts=[results[0].chunk_text],
    subtract_texts=[results[2].chunk_text],
)
```

## `delete()`

Delete a file and all its chunks from the index.

```python
def delete(self, file_path: str) -> bool
```

**Returns:** `True` if deleted, `False` on error.

```python
lens.delete("/Users/me/Documents/old-report.pdf")
```

## `doctor()`

Run health checks on all dependencies.

```python
def doctor(self) -> list[DoctorCheck]
```

**Returns:** `list[`[`DoctorCheck`](/api/data-classes#doctorcheck)`]`

```python
for check in lens.doctor():
    print(f"{check.name}: {check.status} — {check.message}")
```

## Complete example

```python
from locallens import LocalLens, OllamaUnavailableError

# Initialize
lens = LocalLens("~/Documents", ollama_model="qwen2.5:3b")

# Index
result = lens.index()
print(f"Indexed {result.total_files} files")

# Search
results = lens.search("budget projections", top_k=3)
for r in results:
    print(f"  {r.file_name} (score: {r.score})")

# Ask with error handling
try:
    answer = lens.ask("What are the budget projections for next quarter?")
    print(f"\nAnswer: {answer.answer}")
    print(f"Sources: {[s.file_name for s in answer.sources]}")
except OllamaUnavailableError:
    print("Ollama is not running. Start it with: ollama serve")

# Stats
stats = lens.stats()
print(f"\n{stats.total_files} files, {stats.total_chunks} chunks")

# Health check
for check in lens.doctor():
    icon = "✓" if check.status == "ok" else "✗"
    print(f"  {icon} {check.name}: {check.message}")
```
