# LocalLens + OpenClaw

LocalLens ships as an OpenClaw skill for direct integration with the OpenClaw agent.

## Install from ClawHub

Once the skill is published to ClawHub:

```bash
clawhub install locallens
```

## Manual setup

Until the skill is on ClawHub, install it directly from this repo:

```bash
# 1. Install the LocalLens CLI
pip install locallens

# 2. Copy the skill into your OpenClaw skills directory
git clone https://github.com/mahimairaja/locallens.git /tmp/locallens
cp -r /tmp/locallens/openclaw-skill ~/.openclaw/skills/locallens

# 3. Run the setup script
bash ~/.openclaw/skills/locallens/setup.sh
```

## Example usage

Once loaded, OpenClaw can call LocalLens through the `locallens` skill:

- "Index my ~/Documents folder"
- "Search for quarterly revenue reports"
- "Search: auth +middleware -test"
- "Ask: what does the billing module do?"
- "Check the LocalLens doctor status"

The skill translates these to shell commands:

```bash
locallens index ~/Documents --format json
locallens search "quarterly revenue" --format json
locallens ask "what does the billing module do?" --format json
locallens doctor --format json
```

## Source

The skill definition lives in [`openclaw-skill/SKILL.md`](https://github.com/mahimairaja/locallens/blob/main/openclaw-skill/SKILL.md) in the LocalLens repo.

## Links

- [MCP tool reference](/mcp/tools-reference) (for programmatic access instead)
- [Setup details](/mcp/setup)
