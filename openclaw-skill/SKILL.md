---
name: locallens
version: 0.2.0
description: Semantic file search engine for AI agents. Search files by meaning, ask questions with RAG, all 100% offline. Supports query arithmetic (+/- operators).
author: mahimairaja
homepage: https://github.com/mahimairaja/locallens
tags:
  - search
  - semantic-search
  - rag
  - offline
  - files
  - code-search
  - mcp
---

# LocalLens -- Semantic File Search

Search your files by meaning, not just keywords. 100% offline.

## Setup

Ensure LocalLens is installed:

```bash
pip install locallens
```

Optional extras:

- Voice support: `pip install "locallens[voice]"`
- MCP server: `pip install "locallens[mcp]"`
- Rust acceleration (5-10x faster on large corpora): `pip install "locallens[fast]"`

## Usage

### Index a folder

Tell me to index a folder and I will run:

```bash
locallens index /path/to/folder --format json
```

### Search files

Ask me to find files and I will run:

```bash
locallens search "your query" --format json --top-k 10
```

Supports query arithmetic:

- `"auth -test"` finds auth files excluding tests
- `"pricing +recent"` biases toward recent pricing docs
- `'payment +"last quarter" -draft'` -- quoted multi-word terms

### Ask questions

Ask me a question about your files and I will run:

```bash
locallens ask "your question" --format json
```

Requires Ollama running locally (`ollama serve`).

### Check setup

Ask me to check LocalLens setup and I will run:

```bash
locallens doctor --format json
```

## MCP Server

For deeper integration, start the MCP server:

```bash
locallens serve --mcp
```

This exposes tools: `locallens_search`, `locallens_ask`, `locallens_index`, `locallens_status`, `locallens_files`.
