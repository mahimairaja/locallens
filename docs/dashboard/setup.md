# Web Dashboard Setup

The web dashboard is an optional React UI for browsing, searching, and asking questions about your files.

## Quick start

```bash
pip install "locallens[server]"
locallens serve --ui
```

Opens the dashboard at `http://localhost:8000`.

## Docker Compose alternative

The web dashboard can also run with Docker Compose, which includes a Qdrant server:

```bash
git clone https://github.com/mahimairaja/locallens.git
cd locallens
make setup   # starts Qdrant, pulls Ollama model, installs deps
make dev     # starts backend on :8000 and frontend on :5173
```

## Custom port

```bash
locallens serve --ui --port 3000
```

::: tip
The dashboard is secondary to the core engine. For most use cases, the Python library, CLI, or MCP server are simpler and more efficient.
:::
