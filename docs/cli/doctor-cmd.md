# locallens doctor

Run health checks on all LocalLens dependencies.

## Usage

```bash
locallens doctor [OPTIONS]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--format` | `rich` | Output format: `rich` or `json` |

## Checks performed

| Check | Critical? | What it tests |
|---|---|---|
| Qdrant Edge | Yes | Local shard is accessible and contains data |
| Qdrant Server | No | Docker Qdrant is running (only for web dashboard) |
| Ollama | No | Ollama is reachable (only for `ask`) |
| Embedding Model | Yes | Sentence-transformers model loads correctly |
| Voice STT | No | Moonshine speech-to-text is installed |
| Voice TTS | No | Piper text-to-speech is installed |
| Disk Space | No | Sufficient free disk space |

## Examples

```bash
locallens doctor
```

## Rich output

```
┌──────────────────────────────────────────────────────┐
│                  LocalLens Doctor                     │
├─────────────────┬────────┬───────────────────────────┤
│ Check           │ Status │ Detail                    │
├─────────────────┼────────┼───────────────────────────┤
│ Qdrant Edge     │   ✓    │ Shard OK, 1284 points     │
│ Qdrant Server   │   -    │ Not running (optional)    │
│ Ollama          │   ✓    │ Running at localhost:11434 │
│ Embedding Model │   ✓    │ all-MiniLM-L6-v2 (384)    │
│ Voice STT       │   -    │ Not installed (optional)   │
│ Voice TTS       │   -    │ Not installed (optional)   │
│ Disk Space      │   ✓    │ 45.2 GB free              │
└─────────────────┴────────┴───────────────────────────┘
```

## JSON output

```bash
locallens doctor --format json
```

```json
{
  "checks": [
    { "name": "Qdrant Edge", "status": "ok", "message": "1284 points in shard" },
    { "name": "Ollama", "status": "ok", "message": "Running at http://localhost:11434" },
    { "name": "Embedding Model", "status": "ok", "message": "all-MiniLM-L6-v2 (384-dim)" },
    { "name": "Voice STT", "status": "warn", "message": "Not installed (optional)" },
    { "name": "Voice TTS", "status": "warn", "message": "Not installed (optional)" },
    { "name": "Disk Space", "status": "ok", "message": "45.2 GB free" }
  ],
  "exit_code": 0
}
```

The exit code is `0` if all critical checks pass, `1` otherwise. Critical checks are Qdrant Edge and Embedding Model.
