# CLI Commands Overview

The `locallens` CLI is installed automatically with `pip install locallens`.

## Commands

| Command | Description |
|---|---|
| [`index`](/cli/index-cmd) | Index local files into the vector database |
| [`search`](/cli/search-cmd) | Semantic search over indexed files |
| [`ask`](/cli/ask-cmd) | Ask a question using RAG |
| [`stats`](/cli/stats-cmd) | Show collection statistics |
| [`doctor`](/cli/doctor-cmd) | Run health checks |
| [`serve`](/cli/serve-cmd) | Start MCP, API, or UI server |
| `voice` | Start the voice interface |
| `watch` | Watch a folder and re-index on changes |
| `sync pull` | Pull snapshot from remote Qdrant |
| `sync push` | Push local data to remote Qdrant |
| `schema --show` | Print current collection schema |
| `schema --history` | Print all schema versions |

## Global options

All commands support `--format json` for machine-readable output. See [JSON Output](/cli/json-output) for details.

## Quick reference

```bash
# Index a folder
locallens index ~/Documents

# Search
locallens search "meeting notes" --top-k 10

# Ask a question
locallens ask "What was discussed in the Q3 meeting?"

# Check health
locallens doctor

# Start MCP server
locallens serve --mcp
```
