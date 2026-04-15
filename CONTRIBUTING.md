# Contributing to LocalLens

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for Qdrant server)
- [Ollama](https://ollama.ai) (for RAG/ask features)
- Node.js 18+ (for the frontend)

## Setup

```bash
git clone https://github.com/mahimai/ask-local-files.git
cd ask-local-files
pip install -e ".[dev]"
make setup
```

## Running Tests

```bash
make test          # full suite (needs Qdrant running)
make test-quick    # skip Ollama-dependent tests
make lint          # ruff check
```

## Project Structure

| Directory | What it does |
|---|---|
| `locallens/` | CLI tool using Qdrant Edge (no Docker) |
| `backend/` | FastAPI web API using Qdrant Server (Docker) |
| `frontend/` | React 19 + Vite web app |
| `tests/` | Pytest test suite |

The CLI and backend have near-duplicate pipeline modules (extractors, chunker,
embedder, indexer). When fixing a bug, check whether the same change is needed
in both trees.

## Adding an Extractor

1. Create `locallens/extractors/my_format.py`:

```python
from locallens.extractors.base import LocalLensExtractor

class MyFormatExtractor(LocalLensExtractor):
    def supported_extensions(self):
        return [".xyz"]

    def extract(self, file_path):
        return file_path.read_text(encoding="utf-8")

    def name(self):
        return "my_format"
```

2. Register it in `pyproject.toml`:

```toml
[project.entry-points."locallens.extractors"]
my_format = "locallens.extractors.my_format:MyFormatExtractor"
```

3. Run `pip install -e .` to refresh entry points, then verify:

```bash
python -c "from locallens.extractors import get_extractor; print(get_extractor('.xyz'))"
```

## Finding Issues

Check the [GitHub Issues](https://github.com/mahimai/ask-local-files/issues)
page for open tasks. Issues tagged `good first issue` are a good starting point.
