# LocalLens OpenClaw Skill

An OpenClaw skill that lets your agent search, index, and ask questions about local files through LocalLens.

## What this skill provides

- Semantic file search (hybrid + keyword + vector)
- RAG Q&A with source citations
- File indexing with adaptive chunking (PDF, DOCX, code, spreadsheets, email, etc.)
- Query arithmetic (`+`/`-` operators)
- 100% offline

## Install

### From ClawHub (once published)

```bash
clawhub install locallens
```

### Manual setup

```bash
# 1. Install the LocalLens CLI
pip install locallens

# 2. Copy this skill into your OpenClaw skills directory
cp -r openclaw-skill ~/.openclaw/skills/locallens

# 3. Run the setup script
bash ~/.openclaw/skills/locallens/setup.sh
```

## Usage

See `SKILL.md` for the full usage contract. In short: ask the agent to index a folder, then search or ask questions about it.

## Publishing to ClawHub

1. Fork https://github.com/openclaw/clawhub
2. Copy this directory to `skills/locallens/`
3. Open a pull request
4. Wait for review and the automated skill scan

## Links

- GitHub: https://github.com/mahimairaja/locallens
- Docs: https://locallens.mahimai.ca/
- PyPI: https://pypi.org/project/locallens/
