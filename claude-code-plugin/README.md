# LocalLens Claude Code Plugin

Adds `/locallens:*` slash commands to Claude Code for semantic file search, indexing, and RAG Q&A.

## What this plugin does

- `/locallens:search <query>` -- semantic search over your indexed files
- `/locallens:index [path]` -- index a folder for search (defaults to CWD)
- `/locallens:ask <question>` -- RAG Q&A with source citations (requires Ollama)
- `/locallens:doctor` -- health check for dependencies

Supports query arithmetic: `pricing +recent -draft`.

## Requirements

Install the LocalLens CLI:

```bash
pip install locallens
```

For RAG (`/locallens:ask`), install and start Ollama:

```bash
# Install from https://ollama.com, then:
ollama pull qwen2.5:3b
ollama serve
```

## Installation

### Option A: symlink the plugin directory

```bash
mkdir -p ~/.claude/plugins
ln -s "$(pwd)/claude-code-plugin" ~/.claude/plugins/locallens
```

### Option B: copy the plugin directory

```bash
mkdir -p ~/.claude/plugins
cp -r claude-code-plugin ~/.claude/plugins/locallens
```

Restart Claude Code or run `/reload-plugins`. Type `/locallens:` to verify the commands appear.

## Alternative: MCP server

If you prefer programmatic tool access over slash commands, add LocalLens as an MCP server instead:

```bash
claude mcp add locallens -- locallens serve --mcp
```

See the [MCP setup docs](https://locallens.mahimai.ca/mcp/setup) for details.

## Links

- GitHub: https://github.com/mahimairaja/locallens
- Docs: https://locallens.mahimai.ca/
- PyPI: https://pypi.org/project/locallens/
