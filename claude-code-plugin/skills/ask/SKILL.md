---
name: locallens-ask
description: Ask a question about indexed files and get an answer with source citations. Requires Ollama running locally.
command: /locallens:ask
---

Ask a question about indexed files using LocalLens RAG.

```bash
locallens ask "$ARGUMENTS" --format json
```

If the command fails with an Ollama error, tell the user:

> Ollama is not running. Start it with: `ollama serve`
> Then pull a model: `ollama pull qwen2.5:3b`

Present the answer with:
1. The answer text
2. Source files used (with file names and paths)
3. The model used for generation
