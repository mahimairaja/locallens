---
layout: home

hero:
  name: LocalLens
  text: Semantic File Search for AI Agents
  tagline: Index your files. Search by meaning. Ask questions. 100% offline. Ships as a Python library, CLI, and MCP server.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/mahimairaja/locallens
    - theme: alt
      text: PyPI
      link: https://pypi.org/project/locallens/

features:
  - title: Python Library
    details: "from locallens import LocalLens — import it, use it, done. No server, no Docker."
  - title: MCP Server
    details: "locallens serve --mcp — one command to become a tool for Claude Code, Cursor, and any MCP client."
  - title: 100% Offline
    details: "Qdrant Edge + local embeddings + Ollama. Your files never leave your machine."
---

<style>
:root {
  --vp-home-hero-name-color: transparent;
  --vp-home-hero-name-background: linear-gradient(135deg, #C67B3C, #D4934E);
}
</style>

## Quick Examples

::: code-group

```python [Python]
from locallens import LocalLens

lens = LocalLens("~/Documents")
lens.index()
results = lens.search("quarterly revenue report")
print(results[0].file_name, results[0].score)
```

```bash [CLI]
pip install locallens
locallens index ~/Documents
locallens search "quarterly revenue report"
```

```json [MCP (Claude Desktop)]
// ~/.config/claude/claude_desktop_config.json
{
  "mcpServers": {
    "locallens": {
      "command": "locallens",
      "args": ["serve", "--mcp"]
    }
  }
}
```

:::
