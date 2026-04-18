# MCP Server Setup

LocalLens ships as an MCP (Model Context Protocol) server, letting AI agents like Claude Code and Claude Desktop search your files.

## Install

```bash
pip install "locallens[mcp]"
```

## Start

```bash
locallens serve --mcp
```

The server starts on port `8811` by default, using SSE transport.

## Custom port

```bash
locallens serve --mcp --port 9000
```

## Environment variables

Configure the MCP server via environment variables:

| Variable | Default | Description |
|---|---|---|
| `LOCALLENS_DATA_DIR` | `~/.locallens` | Data directory |
| `LOCALLENS_COLLECTION` | `locallens` | Collection name |
| `LOCALLENS_OLLAMA_URL` | `http://localhost:11434` | Ollama URL |
| `LOCALLENS_OLLAMA_MODEL` | `qwen2.5:3b` | Ollama model |
| `LOCALLENS_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |

## Verify

Once running, the server prints:

```
LocalLens MCP server running on http://localhost:8811/sse
```

You can test the SSE endpoint:

```bash
curl http://localhost:8811/sse
```

## Index first

The MCP server searches whatever is already indexed. Index your files before starting:

```bash
locallens index ~/my-project
locallens serve --mcp
```

Or use the `locallens_index` tool from within your AI client to index on demand.
