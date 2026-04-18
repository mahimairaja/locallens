# JSON Output

All CLI commands support `--format json` for machine-readable output.

## How it works

- **stdout** contains clean JSON only
- Progress messages and warnings go to **stderr**
- Exit code follows standard conventions (0 = success, 1 = error)

## Examples by command

### index

```bash
locallens index ~/Documents --format json
```

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

### search

```bash
locallens search "revenue" --format json
```

```json
[
  {
    "file_path": "/Users/me/Documents/report.pdf",
    "file_name": "report.pdf",
    "file_type": ".pdf",
    "chunk_text": "Q3 revenue exceeded projections by 12%...",
    "chunk_index": 3,
    "score": 0.8742,
    "extractor": "pymupdf"
  }
]
```

### ask

```bash
locallens ask "What was Q3 revenue?" --format json
```

```json
{
  "answer": "Q3 revenue was $4.2M, exceeding projections by 12%.",
  "sources": [...],
  "model": "qwen2.5:3b",
  "duration_seconds": 5.23
}
```

### stats

```bash
locallens stats --format json
```

```json
{
  "total_files": 42,
  "total_chunks": 1284,
  "file_types": { ".pdf": 450, ".py": 320 },
  "collection_name": "locallens",
  "data_dir": "/Users/me/.locallens"
}
```

### doctor

```bash
locallens doctor --format json
```

```json
{
  "checks": [
    { "name": "Qdrant Edge", "status": "ok", "message": "1284 points in shard" }
  ],
  "exit_code": 0
}
```

## Piping to jq

```bash
# Get the top result's file name
locallens search "revenue" --format json | jq '.[0].file_name'

# Get all unique file types in results
locallens search "config" --format json | jq '[.[].file_type] | unique'

# Pretty-print the answer
locallens ask "What is this project?" --format json | jq '.answer'
```

## Scripting example

Extract file paths from search results and process them:

```bash
#!/bin/bash
# Find files related to a topic and copy them
locallens search "authentication" --format json \
  | jq -r '.[].file_path' \
  | sort -u \
  | while read -r path; do
      echo "Found: $path"
      cp "$path" ./collected/
    done
```
