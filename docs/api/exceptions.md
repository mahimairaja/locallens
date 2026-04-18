# Exceptions

## OllamaUnavailableError

Raised when Ollama is not reachable. This happens when calling `ask()` or `ask_stream()` without Ollama running.

```python
from locallens import OllamaUnavailableError
```

### When it's raised

- `LocalLens.ask()` — when Ollama is not running or unreachable
- `LocalLens.ask_stream()` — when Ollama is not running or unreachable

### Default message

```
Ollama is not running. Start it with: ollama serve
```

### Handling

```python
from locallens import LocalLens, OllamaUnavailableError

lens = LocalLens("~/Documents")

try:
    result = lens.ask("What was the Q3 revenue?")
    print(result.answer)
except OllamaUnavailableError:
    print("Ollama is not running.")
    print("Start it with: ollama serve")
    print("Pull a model with: ollama pull qwen2.5:3b")
```

::: tip
Search, index, stats, files, delete, and doctor **do not** require Ollama. Only `ask()` and `ask_stream()` need it.
:::
