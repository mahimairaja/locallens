# locallens ask

Ask a question about your indexed files using RAG (Retrieval Augmented Generation).

## Usage

```bash
locallens ask <question> [OPTIONS]
```

## Arguments

| Argument | Required | Description |
|---|---|---|
| `question` | Yes | The question to ask about your files |

## Options

| Option | Default | Description |
|---|---|---|
| `--top-k` | `8` | Number of chunks to retrieve for context |
| `--namespace` | `default` | Namespace to query |
| `--format` | `rich` | Output format: `rich` or `json` |

## Prerequisites

Requires [Ollama](https://ollama.com) running locally:

```bash
ollama pull qwen2.5:3b
ollama serve
```

## Examples

```bash
# Ask a question
locallens ask "What was the Q3 revenue?"

# Use more context chunks
locallens ask "Summarize the project architecture" --top-k 15
```

## Rich output

In rich mode, the answer streams token by token to the terminal.

## JSON output

```bash
locallens ask "What was the Q3 revenue?" --format json
```

```json
{
  "answer": "Based on the report, Q3 revenue was $4.2M, exceeding projections by 12%.",
  "sources": [
    {
      "file_path": "/Users/me/Documents/report.pdf",
      "file_name": "report.pdf",
      "file_type": ".pdf",
      "chunk_text": "Q3 revenue exceeded projections...",
      "chunk_index": 3,
      "score": 0.8742,
      "extractor": "pymupdf"
    }
  ],
  "model": "qwen2.5:3b",
  "duration_seconds": 5.23
}
```
