# Configuration

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `LOCALLENS_DATA_DIR` | `~/.locallens` | Directory for Qdrant Edge shard and BM25 index |
| `LOCALLENS_COLLECTION` | `locallens` | Qdrant collection name |
| `LOCALLENS_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `LOCALLENS_OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model for RAG |
| `LOCALLENS_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `QDRANT_SYNC_URL` | _(unset)_ | Remote Qdrant server for sync |
| `QDRANT_SYNC_API_KEY` | _(unset)_ | API key for remote Qdrant |

## Example `.env` file

```bash
LOCALLENS_DATA_DIR=~/.locallens
LOCALLENS_OLLAMA_URL=http://localhost:11434
LOCALLENS_OLLAMA_MODEL=qwen2.5:3b
LOCALLENS_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Data directory structure

```
~/.locallens/
├── qdrant_data/          # Qdrant Edge shard files
│   ├── segments/
│   └── ...
└── bm25_index/           # BM25 keyword index
```

## Custom embedding model

You can use any sentence-transformers compatible model:

```python
lens = LocalLens(
    "~/Documents",
    embedding_model="BAAI/bge-small-en-v1.5"
)
```

Or via environment variable:

```bash
export LOCALLENS_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

::: warning
Changing the embedding model requires re-indexing all files. Delete the existing shard first:

```bash
rm -rf ~/.locallens/qdrant_data
locallens index ~/Documents
```
:::

## Custom Ollama model

Any Ollama model works for RAG:

```python
lens = LocalLens(
    "~/Documents",
    ollama_model="llama3.2:3b"
)
```

Or via environment variable:

```bash
export LOCALLENS_OLLAMA_MODEL=llama3.2:3b
ollama pull llama3.2:3b
```
