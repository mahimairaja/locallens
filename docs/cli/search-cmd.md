# locallens search

Semantic search over your indexed files. Supports query arithmetic with `+` and `-` operators to add or subtract concepts from the search direction.

## Usage

```bash
locallens search <query> [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `query` | Yes | The search query |

## Options

| Option | Default | Description |
|---|---|---|
| `--top-k` | `5` | Number of results to return |
| `--file-type` | _(none)_ | Filter by extension, e.g. `.pdf` |
| `--path-prefix` | _(none)_ | Filter by file path prefix |
| `--namespace` | `default` | Namespace to search |
| `--format` | `rich` | Output format: `rich` or `json` |

## Examples

```bash
# Basic search
locallens search "quarterly revenue report"

# Get more results
locallens search "authentication" --top-k 20

# Filter by file type
locallens search "budget" --file-type .pdf

# Search with path filter
locallens search "API endpoints" --path-prefix /Users/me/project/src

# Query arithmetic: boost and suppress concepts
locallens search "pricing strategy +recent -draft"

# Multiple subtractions
locallens search "authentication -test -mock +production"

# Quoted phrases
locallens search '+"machine learning" -"neural networks" +transformers'
```

## Rich output

```
┌──────────────────────────────────────────────────────┐
│                   Search Results                      │
├────┬───────┬──────────────┬──────────┬───────────────┤
│ #  │ Score │ File         │ Path     │ Preview       │
├────┼───────┼──────────────┼──────────┼───────────────┤
│ 1  │ 0.87  │ report.pdf   │ /Users/… │ Q3 revenue …  │
│ 2  │ 0.74  │ notes.md     │ /Users/… │ Meeting notes…│
└────┴───────┴──────────────┴──────────┴───────────────┘
```

## JSON output

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
