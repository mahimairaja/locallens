---
layout: home

hero:
  name: LocalLens
  text: Semantic File Search for AI Agents
  tagline: Index, search, and ask questions about your local files. Ships as a Python library, CLI, and MCP server. 100% offline.
  image:
    src: /hero.svg
    alt: LocalLens pipeline illustration
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
    details: "from locallens import LocalLens -- import it, use it, done. No server, no Docker needed."
  - title: MCP Server
    details: "locallens serve --mcp -- one command to become a tool for Claude Code, Cursor, and any MCP client."
  - title: 100% Offline
    details: "Qdrant Edge + local embeddings + Ollama. Your files never leave your machine. Zero network calls."
---

## Install in 10 seconds

```bash
pip install locallens
```

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
locallens index ~/Documents
locallens search "quarterly revenue report"
locallens ask "What was the Q3 revenue?"
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

## Powered by

<div style="display: flex; gap: 2rem; justify-content: center; align-items: center; padding: 1.5rem 0; flex-wrap: wrap;">
  <span style="font-family: var(--vp-font-family-mono); font-size: 0.95rem; color: var(--vp-c-text-1); font-weight: 500;">Qdrant Edge</span>
  <span style="color: var(--vp-c-text-3);">|</span>
  <span style="font-family: var(--vp-font-family-mono); font-size: 0.95rem; color: var(--vp-c-text-1); font-weight: 500;">sentence-transformers</span>
  <span style="color: var(--vp-c-text-3);">|</span>
  <span style="font-family: var(--vp-font-family-mono); font-size: 0.95rem; color: var(--vp-c-text-1); font-weight: 500;">Ollama</span>
  <span style="color: var(--vp-c-text-3);">|</span>
  <span style="font-family: var(--vp-font-family-mono); font-size: 0.95rem; color: var(--vp-c-text-1); font-weight: 500;">PyO3 + Rust</span>
</div>
