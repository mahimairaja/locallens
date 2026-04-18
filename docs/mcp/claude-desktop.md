# Claude Desktop Integration

Use LocalLens with [Claude Desktop](https://claude.ai/download) to search your local files from the Claude chat interface.

## Setup

1. Install LocalLens with MCP support:

```bash
pip install "locallens[mcp]"
```

2. Index your files:

```bash
locallens index ~/Documents
```

3. Add to your Claude Desktop config:

### macOS

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

### Windows

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

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

4. Restart Claude Desktop.

## Verify the connection

After restarting Claude Desktop:

1. Open a new conversation
2. Look for the tools icon (hammer) in the input area
3. You should see LocalLens tools listed: `locallens_search`, `locallens_ask`, `locallens_index`, `locallens_status`, `locallens_files`

## Example conversation

**You:** "Search my documents for anything about the Q3 budget"

**Claude:** _Uses locallens_search to find relevant documents, then summarizes the results._

**You:** "What were the key takeaways from that budget meeting?"

**Claude:** _Uses locallens_ask to generate an answer with source citations._

## Troubleshooting

- **Tools not showing up?** Make sure the config JSON is valid and `locallens` is on your PATH. Try running `locallens serve --mcp` in a terminal to verify it starts.
- **"Ollama not available" errors?** The `ask` tool requires Ollama. Search, index, and status work without it.
- **Empty results?** Make sure you've indexed your files first: `locallens index ~/Documents`
