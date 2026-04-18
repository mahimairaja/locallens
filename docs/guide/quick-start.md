# Quick Start

Pick the path that matches how you want to use LocalLens.

## Path 1: Python library

Search your files from Python code.

```python
from locallens import LocalLens

# Create an instance pointing at your files
lens = LocalLens("~/Documents")

# Index the folder (skips unchanged files automatically)
result = lens.index()
print(f"Indexed {result.total_files} files, {result.total_chunks} chunks")

# Semantic search
results = lens.search("quarterly revenue report")
for r in results:
    print(f"  {r.file_name} — score {r.score:.2f}")
    print(f"  {r.chunk_text[:100]}...")

# Ask a question (requires Ollama running)
answer = lens.ask("What was the Q3 revenue?")
print(answer.answer)
for source in answer.sources:
    print(f"  Source: {source.file_name}")
```

## Path 2: CLI tool

Search your files from the terminal.

```bash
# Install
pip install locallens

# Index a folder
locallens index ~/Documents

# Search
locallens search "quarterly revenue report"

# Ask a question (requires ollama serve)
locallens ask "What was the Q3 revenue?"

# Check health
locallens doctor

# Get stats
locallens stats
```

All commands support `--format json` for scripting:

```bash
locallens search "revenue" --format json | jq '.[0].file_name'
```

## Path 3: MCP server for AI agents

Let Claude Code, Claude Desktop, or Cursor search your files.

```bash
# Install with MCP support
pip install "locallens[mcp]"

# Index your project first
locallens index ~/my-project

# Start the MCP server
locallens serve --mcp
```

Add to Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

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

Now Claude can search your indexed files, ask questions about them, and check index status — all running locally on your machine.
