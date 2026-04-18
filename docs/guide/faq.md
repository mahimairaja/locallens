# FAQ

## Do I need Docker?

No. The Python library and CLI use **Qdrant Edge**, an embedded vector database that runs in-process. Docker is only needed for the web dashboard, which uses a Qdrant server container.

## Do I need Ollama?

Only for the `ask` / RAG feature. **Search, index, stats, and doctor all work without Ollama.** Install Ollama only when you want to ask natural language questions about your files.

## How much RAM does it need?

About 2-3 GB with everything loaded (embedding model + Qdrant Edge shard). 4 GB recommended. The embedding model (`all-MiniLM-L6-v2`) is small at 80 MB.

## Does it work on Windows?

Yes. LocalLens works on Python 3.11+ on Windows, macOS, and Linux. The voice feature (`moonshine-voice`, `piper-tts`) works best on macOS and Linux.

## Can I use a different LLM?

Yes. Any Ollama model works. Set the model when creating the instance:

```python
lens = LocalLens("~/Documents", ollama_model="llama3.2:3b")
```

Or via environment variable:

```bash
export LOCALLENS_OLLAMA_MODEL=llama3.2:3b
```

## Can I use a different embedding model?

Yes. Any sentence-transformers compatible model works:

```python
lens = LocalLens("~/Documents", embedding_model="BAAI/bge-small-en-v1.5")
```

::: warning
Changing the embedding model requires re-indexing. Delete `~/.locallens/qdrant_data` and re-run `locallens index`.
:::

## How do I update the index when files change?

Re-run `locallens index <folder>`. It uses content hashing to automatically skip unchanged files — only new or modified files get re-indexed. Use `--force` to re-index everything.

For automatic re-indexing, use watch mode:

```bash
locallens watch ~/Documents
```

## Is my data sent anywhere?

No. Everything runs on your machine:
- Embeddings computed locally via sentence-transformers
- Vector storage in Qdrant Edge (a file on disk)
- LLM inference via local Ollama

Zero network calls. No cloud APIs. No telemetry.

## How is this different from other file search tools?

LocalLens combines several capabilities in one offline package:
- **Hybrid search** (semantic + BM25 with RRF fusion)
- **RAG Q&A** with source citations
- **Voice interface** (STT + TTS)
- **MCP server** for AI agent integration
- **Structured JSON output** for scripting
- **Plugin extractors** for custom file formats
