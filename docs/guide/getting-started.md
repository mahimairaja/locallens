# Getting Started

Install LocalLens in 10 seconds and run your first search.

## 1. Install

```bash
pip install locallens
```

## 2. Index a folder

```bash
locallens index ~/Documents
```

Or from Python:

```python
from locallens import LocalLens

lens = LocalLens("~/Documents")
result = lens.index()
print(f"Indexed {result.total_files} files ({result.total_chunks} chunks)")
```

## 3. Search

```bash
locallens search "meeting notes from last week"
```

Or from Python:

```python
results = lens.search("meeting notes from last week")
for r in results:
    print(f"{r.file_name} (score: {r.score:.2f})")
```

## Verify your setup

Run the doctor command to check that everything is working:

```bash
locallens doctor
```

Example output:

```text
┌───────────────────────────────────────────────────────────┐
│                    LocalLens Doctor                        │
├─────────────────┬────────┬────────────────────────────────┤
│ Check           │ Status │ Detail                         │
├─────────────────┼────────┼────────────────────────────────┤
│ Qdrant Edge     │   ✓    │ Shard OK, 1284 points          │
│ Ollama          │   ✓    │ Running at localhost:11434      │
│ Embedding Model │   ✓    │ all-MiniLM-L6-v2 (384-dim)     │
│ Voice STT       │   -    │ Not installed (optional)        │
│ Voice TTS       │   -    │ Not installed (optional)        │
│ Disk Space      │   ✓    │ 45.2 GB free                   │
│ Rust Extensions │   ✓    │ Active: BM25, Chunker, Walker  │
│ Schema Version  │   ✓    │ v1 (7 fields)                  │
└─────────────────┴────────┴────────────────────────────────┘
```

## Next steps

- [Installation](/guide/installation) — all install options (voice, MCP, server, from source)
- [Quick Start](/guide/quick-start) — complete walkthroughs for Python, CLI, and MCP
- [Architecture](/guide/architecture) — how LocalLens works under the hood
