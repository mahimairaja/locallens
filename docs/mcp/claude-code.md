# Claude Code Integration

Use LocalLens as an MCP server in [Claude Code](https://claude.ai/code) to let Claude search and understand your local files.

## Setup

1. Install LocalLens with MCP support:

```bash
pip install "locallens[mcp]"
```

2. Index your project:

```bash
locallens index ~/my-project
```

3. Add to your Claude Code MCP config:

```bash
claude mcp add locallens -- locallens serve --mcp
```

Or manually add to your Claude Code settings:

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

## Example prompts

Once connected, you can ask Claude things like:

- **"Find all files related to authentication in this project"** — triggers `locallens_search`
- **"Summarize what the payment module does"** — triggers `locallens_ask`
- **"What test files exist and what do they cover?"** — triggers `locallens_search` with file type filter
- **"Index the src/ folder"** — triggers `locallens_index`
- **"How many files are indexed?"** — triggers `locallens_status`

## Tips

- **Index before you search.** Claude can index folders for you via the `locallens_index` tool, but pre-indexing is faster.
- **Be specific in your questions.** "What does the auth middleware do?" works better than "tell me about auth."
- **Use file type hints.** "Find Python files about database migrations" helps Claude pass `file_type=".py"` to narrow results.
- **Re-index after big changes.** If you've made significant changes to your project, re-index to update the search database.

## Environment variables

Pass environment variables to customize the MCP server:

```json
{
  "mcpServers": {
    "locallens": {
      "command": "locallens",
      "args": ["serve", "--mcp"],
      "env": {
        "LOCALLENS_OLLAMA_MODEL": "llama3.2:3b"
      }
    }
  }
}
```
