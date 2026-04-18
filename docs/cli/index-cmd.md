# locallens index

Index local files into the vector database for semantic search.

## Usage

```bash
locallens index <folder_path> [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `folder_path` | Yes | Path to the folder to index |

## Options

| Option | Default | Description |
|---|---|---|
| `--force` | `false` | Re-index all files, ignoring hash cache |
| `--namespace` | `default` | Namespace to index into |
| `--format` | `rich` | Output format: `rich` or `json` |

## Examples

```bash
# Index a folder
locallens index ~/Documents

# Force re-index everything
locallens index ~/Documents --force

# Index into a specific namespace
locallens index ~/project --namespace myproject
```

## JSON output

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

## How it works

1. Scans the folder recursively for supported file types
2. Computes a SHA-256 hash of each file's content
3. Skips files whose hash already exists in the index (unless `--force`)
4. Extracts text using the appropriate extractor
5. Chunks text into ~500 character segments with 50 character overlap
6. Embeds each chunk using sentence-transformers
7. Upserts into Qdrant with deterministic point IDs
