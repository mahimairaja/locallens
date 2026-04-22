# LocalLens + Windsurf

Add LocalLens to Windsurf as an MCP server for semantic code search and RAG Q&A.

## Prerequisites

```bash
pip install "locallens[mcp]"
locallens index ~/my-project
```

## Configure Windsurf

Add LocalLens to your Windsurf MCP config (`~/.codeium/windsurf/mcp_config.json` on macOS/Linux, `%APPDATA%\Codeium\Windsurf\mcp_config.json` on Windows):

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

Restart Windsurf. The five LocalLens tools appear in the MCP tool picker: `locallens_search`, `locallens_ask`, `locallens_index`, `locallens_status`, `locallens_files`.

## Example usage

- "Find auth-related files but skip test files" → triggers `locallens_search` with query arithmetic
- "Summarize what the payment module does" → triggers `locallens_ask`
- "How many files are indexed right now?" → triggers `locallens_status`

## Tips

- Point Windsurf at a pre-indexed folder -- Windsurf can run `locallens_index` itself, but pre-indexing is faster for large repos.
- Use file type filters in your prompts: "Find Python files about database migrations" will pass `file_type: ".py"` to the search tool.

## Links

- [MCP tool reference](/mcp/tools-reference)
- [Setup details](/mcp/setup)
