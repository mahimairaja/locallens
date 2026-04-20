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

## Working on the Rust extension

LocalLens ships a compiled PyO3 extension (`locallens._locallens_rs`) for
performance-critical modules. BM25 is the first — chunker and file-walker
will follow. The Python fallback (`locallens/_bm25_core.py`, …) is still
present and used when the extension can't be loaded (sdist install
without rustc, unsupported platform), so a contributor without Rust can
still run the full test suite minus the Rust parity tests.

### Setting up a local dev env

1. Install rustup: <https://rustup.rs>
2. `rustup toolchain install stable`
3. `cargo --version` — sanity check.
4. `pip install -e ".[dev]"` — installs maturin + the usual test tooling.
5. `maturin develop --release` — builds the extension into the active
   venv. Re-run after any change to `src/*.rs`, `Cargo.toml`, or
   `pyproject.toml`.

### Verifying the extension is live

```bash
python -c "from locallens._rust import HAS_RUST_BM25; print(HAS_RUST_BM25)"
# True  — the Python wrapper in locallens/bm25.py now delegates to Rust.
```

If it prints `False`, the extension isn't importable — re-run `maturin
develop` and check for build errors.

### Running the Rust side of the test suite

- `cargo test --lib` — unit tests inside `src/bm25.rs`.
- `pytest tests/test_bm25.py -v` — exercises both implementations. The
  parity tests (`test_rust_python_search_parity`, `test_rust_reads_python_json`,
  `test_python_reads_rust_json`) auto-skip when the extension isn't built.

### Release / wheel build

Wheels are built by `.github/workflows/wheels.yml` on every tagged
release. It publishes to PyPI via Trusted Publishing (no token secret
required) and uses `abi3-py311`, so a single wheel per (os, arch) covers
Python 3.11–3.13. The older `publish.yml` is gone — all release
engineering is now in `wheels.yml`.

## Finding Issues

Check the [GitHub Issues](https://github.com/mahimai/ask-local-files/issues)
page for open tasks. Issues tagged `good first issue` are a good starting point.
