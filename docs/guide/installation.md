# Installation

## Basic install

The base install gives you the Python library, CLI, and semantic search. No Docker required.

```bash
pip install locallens
```

This includes:
- `LocalLens` Python API
- `locallens` CLI
- Qdrant Edge (embedded vector database)
- Sentence-transformers embeddings (all-MiniLM-L6-v2)
- Extractors for PDF, DOCX, code, text, spreadsheets

## With LLM support (RAG Q&A)

The `ask` command requires [Ollama](https://ollama.com) running locally. Install Ollama separately, then pull a model:

```bash
# Install Ollama from https://ollama.com
ollama pull qwen2.5:3b
ollama serve
```

No extra Python packages needed — LocalLens talks to Ollama over HTTP.

## With voice

Adds speech-to-text (Moonshine) and text-to-speech (Piper) for the voice interface:

```bash
pip install "locallens[voice]"
```

## With MCP server

Exposes LocalLens as tools for Claude Code, Claude Desktop, Cursor, and other MCP clients:

```bash
pip install "locallens[mcp]"
```

## With web dashboard

Full React web UI with FastAPI backend:

```bash
pip install "locallens[server]"
```

## Everything

Install all optional dependencies at once:

```bash
pip install "locallens[all]"
```

## From source

```bash
git clone https://github.com/mahimairaja/locallens.git
cd locallens
pip install -e ".[all]"
```

## System requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11+ | 3.12+ |
| RAM | 2 GB | 4 GB |
| OS | macOS, Linux, Windows | macOS (Apple Silicon) |
| Docker | Not required | For web dashboard only |
| Ollama | Not required | For `ask` / RAG feature |
