# locallens stats

Show statistics about the indexed collection.

## Usage

```bash
locallens stats [OPTIONS]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--namespace` | `default` | Namespace to show stats for |
| `--format` | `rich` | Output format: `rich` or `json` |

## Examples

```bash
locallens stats
```

## Rich output

```
┌──────────────────────────────────────────┐
│    LocalLens Stats (namespace: default)   │
├──────────────────────┬───────────────────┤
│ Metric               │ Value             │
├──────────────────────┼───────────────────┤
│ Total files indexed  │ 42                │
│ Total chunks         │ 1284              │
│ Storage path         │ ~/.locallens/…    │
│ Disk usage           │ 12.4 MB           │
└──────────────────────┴───────────────────┘

┌──────────────────────────┐
│   File type breakdown    │
├──────────┬───────────────┤
│ Type     │ Chunks        │
├──────────┼───────────────┤
│ .pdf     │ 450           │
│ .py      │ 320           │
│ .md      │ 280           │
│ .txt     │ 234           │
└──────────┴───────────────┘
```

## JSON output

```bash
locallens stats --format json
```

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
