# locallens serve

Start LocalLens servers for AI agents, REST API, or web dashboard.

## Usage

```bash
locallens serve [OPTIONS]
```

## Options

| Option | Description | Extra required |
|---|---|---|
| `--mcp` | Start MCP server for AI agents | `locallens[mcp]` |
| `--api` | Start headless REST API server | `locallens[server]` |
| `--ui` | Start full web dashboard with React UI | `locallens[server]` |
| `--port` | Custom port (default varies by mode) | — |

## MCP server

```bash
pip install "locallens[mcp]"
locallens serve --mcp
```

Default port: `8811`. Exposes LocalLens as tools for Claude Code, Claude Desktop, Cursor, and other MCP clients.

See [MCP Setup](/mcp/setup) for detailed configuration.

## REST API server

```bash
pip install "locallens[server]"
locallens serve --api
```

Default port: `8000`. Headless FastAPI server with search, index, ask, and stats endpoints.

## Web dashboard

```bash
pip install "locallens[server]"
locallens serve --ui
```

Default port: `8000`. Full React web UI served from the FastAPI backend. Includes dashboard, search, ask, and voice pages.

## Custom port

```bash
locallens serve --mcp --port 9000
locallens serve --api --port 3000
locallens serve --ui --port 5000
```
