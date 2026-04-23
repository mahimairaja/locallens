# LocalLens + Cursor

Add LocalLens to Cursor as an MCP server so Cursor can search, index, and ask questions about your local files.

## Prerequisites

```bash
pip install "locallens[mcp]"
locallens index ~/my-project   # index something first
```

## Configure Cursor

Add the following to `.cursor/mcp.json` in your project (or `~/.cursor/mcp.json` globally):

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

Reload Cursor. Open the MCP tools panel -- you should see `locallens_search`, `locallens_ask`, `locallens_index`, `locallens_status`, and `locallens_files`.

## Example prompts

- "Find files in this repo that deal with authentication"
- "What does the payment module do? Cite the files."
- "Search for API endpoint definitions, excluding tests"
- "Ask: how is caching configured in this codebase?"

Cursor will call LocalLens tools automatically based on intent.

## Tips

- Use query arithmetic: `"auth +middleware -test"` narrows the search direction in embedding space.
- Re-index after big code changes: tell Cursor to run `locallens_index` on your project root.
- For multi-project setups, start one MCP server per project using namespaces (`locallens index ~/proj-a --namespace proj-a`).

## Links

- [MCP tool reference](/mcp/tools-reference)
- [Setup details](/mcp/setup)
