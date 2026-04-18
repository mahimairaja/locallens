# Custom MCP Clients

LocalLens's MCP server works with any MCP-compatible client, not just Claude.

## Transport

LocalLens uses **SSE (Server-Sent Events)** transport on port `8811` by default.

```
http://localhost:8811/sse
```

## Connecting from any MCP client

Any client that supports the MCP protocol can connect:

```python
# Example using the mcp Python SDK
from mcp import ClientSession
from mcp.client.sse import sse_client

async with sse_client("http://localhost:8811/sse") as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # List available tools
        tools = await session.list_tools()

        # Call a tool
        result = await session.call_tool(
            "locallens_search",
            arguments={"query": "authentication", "top_k": 5}
        )
```

## Available tools

| Tool | Description |
|---|---|
| `locallens_search` | Search indexed files |
| `locallens_ask` | Ask a question with RAG |
| `locallens_index` | Index a folder |
| `locallens_status` | Get status and health |
| `locallens_files` | List indexed files |

See [Tools Reference](/mcp/tools-reference) for full parameter and response documentation.

## Running as a background service

For always-on access:

```bash
# Start in the background
nohup locallens serve --mcp > /tmp/locallens-mcp.log 2>&1 &

# Or with a custom port
nohup locallens serve --mcp --port 9000 > /tmp/locallens-mcp.log 2>&1 &
```

## Cursor integration

Add to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "locallens": {
      "command": "locallens",
      "args": ["serve", "--mcp"]
    }
  }
}
```
