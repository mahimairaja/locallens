# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LocalLens is a 100% offline semantic file search engine for AI agents. It ships as a **Python library**, **CLI**, **MCP server**, and optional **web dashboard**. The pipeline is: extract, chunk, embed, store (Qdrant), search/RAG (Ollama).

Three consumption layers, one engine:

1. **`locallens/engine.py`** (`LocalLens` class) — the Python API. Everything else calls this.
2. **`locallens/cli.py`** — Typer CLI (`locallens` entrypoint). All commands support `--format json`.
3. **`locallens/mcp_server.py`** — FastMCP server exposing 5 tools for Claude Code, Cursor, etc.

Optional extras:
- **`locallens/dashboard.py`** — Uvicorn server, optionally mounts the React frontend.
- **`backend/` (FastAPI) + `frontend/` (React + Vite)** — full web UI that talks to a Qdrant HTTP server in Docker.

**Docs site:** `docs/` contains a VitePress site deployed to GitHub Pages at `https://mahimairaja.github.io/locallens/`. Built with `make docs-build`.

## Common Commands

### CLI app (`locallens/`)
```bash
pip install -e .               # core install
pip install -e ".[all]"        # everything (voice, mcp, server, parsing, etc.)
locallens index <folder>       # build the index
locallens search "query"
locallens ask "question"       # requires `ollama serve` + `qwen2.5:3b`
locallens stats
locallens doctor               # health checks
locallens serve --mcp          # MCP server for AI agents
locallens serve --api          # headless REST API
locallens serve --ui           # web dashboard
locallens voice
locallens watch <folder>
```

### Web app (`backend/` + `frontend/`)
```bash
make setup    # starts qdrant container, pulls ollama model, installs deps
make dev      # starts qdrant, uvicorn on :8000 (background), vite on :5173
make stop     # docker compose down + pkill uvicorn
```

### Testing and linting
```bash
make test                      # full test suite (pytest, starts Qdrant if needed)
make test-quick                # skip slow (Ollama-dependent) tests
make lint                      # ruff check
ruff check .                   # lint
ruff format .                  # format
mypy locallens/                # type check
```

### Documentation
```bash
make docs                      # VitePress dev server
make docs-build                # VitePress production build -> docs/.vitepress/dist/
cd docs && npm run docs:dev    # alternative
```

### Pre-commit
```bash
pre-commit install             # set up hooks
pre-commit run --all-files     # run all hooks manually
```

Hooks: trailing-whitespace, end-of-file-fixer, check-toml, check-yaml, check-added-large-files, ruff (with --fix), ruff-format.

### Workflow summary

| Change Type | Commands to Run |
|---|---|
| Python code only | `make test` |
| Rust code only | `make rust-dev && make rust-test` |
| Both Rust and Python | `make rust-dev && make rust-test && make test` |
| Frontend only | `cd frontend && npm run build` |
| Documentation only | `cd docs && npm run docs:build` |

### Code structure

```
locallens/
  engine.py           LocalLens class (public API)
  cli.py              Typer CLI entry point
  config.py           Configuration
  models.py           Shared dataclasses
  fast.py             Rust/Python fallback dispatcher
  pipeline/           Core search pipeline
    store.py          Qdrant operations
    indexer.py        File indexing
    searcher.py       Search (semantic + hybrid)
    embedder.py       Embeddings
    chunker.py        Text chunking
    bm25.py           BM25 keyword index
    rag.py            RAG with Ollama
    schema.py         Schema versioning
  extractors/         File type extractors
  serve/              Server modes
    mcp_server.py     MCP server for agents
    dashboard.py      Web dashboard
  integrations/       Optional features
    voice.py          Voice I/O
    sync.py           Qdrant sync
  _internals/         Rust bindings (private)
backend/              FastAPI web backend
frontend/             React web app
rust/                 Rust workspace (performance extensions)
  core/               Shared types
  bm25/               BM25 index and query
  chunker/            Language-aware text chunking
  walker/             Parallel file walking
  watcher/            File system watching
  bridge/             PyO3 Python bindings
tests/                Python test suite
benchmarks/           Performance benchmarks and findings
docs/                 VitePress documentation site
scripts/              Utility scripts
assets/               Logo and demo GIF
```

### Key concepts

- **Engine-first**: LocalLens is a Python library at the core (`locallens.engine.LocalLens`). The CLI, MCP server, and REST API are thin consumers.
- **Rust extensions are optional**: `pip install "locallens[fast]"` installs `locallens-core` (the Rust package). Without it, pure Python works identically, just slower.
- **Fallback pattern**: `locallens.fast` tries `import locallens_core`, falls back to pure Python. `locallens._rust` exposes `HAS_RUST_*` flags for granular detection.
- **Schema evolution**: `locallens/schema.py` tracks Qdrant collection payload schema versions across updates. Additive changes auto-migrate, breaking changes refuse to start.

## Architecture Notes

### Engine-first design
`locallens/engine.py::LocalLens` is the single source of truth. The CLI, MCP server, dashboard, and REST API are thin wrappers that call engine methods: `index()`, `search()`, `ask()`, `ask_stream()`, `stats()`, `files()`, `delete()`, `doctor()`.

### Two stores, two SDKs, one schema
- **CLI / Qdrant Edge** (`locallens/store.py` + `locallens/config.py`): `EdgeShard.create(path, EdgeConfig(...))` from `qdrant-edge-py`. Shard lives under `~/.locallens/qdrant_data`. Module uses an `atexit` hook to call `edge_shard.optimize()` and `.close()` on interpreter shutdown.
- **Backend / `qdrant-client` HTTP** (`backend/app/services/store.py` + `backend/app/config.py`): `QdrantClient(url=..., check_compatibility=False)`, `pydantic_settings.BaseSettings` reads `.env` from repo root (`model_config = {"env_file": "../.env"}`). Collection lives in the Docker volume `./data/qdrant`.

Both trees have near-duplicate pipeline modules (`indexer.py`, `extractors/`, `embedder.py`, chunker logic). When fixing a bug or changing pipeline behavior, **check whether the same change is needed in both trees**.

**Shared schema** (keep in sync or push-sync will fail):
- Collection name: `locallens`
- Named vector key: `"text"` (CLI: `locallens.config.VECTOR_NAME`; backend: `settings.vector_name`)
- Vector params: `size=384`, `distance=Cosine`, via `all-MiniLM-L6-v2`
- Payload fields: `file_path`, `file_name`, `file_type`, `chunk_index`, `chunk_text`, `file_hash`, `indexed_at`
- Keyword payload indexes on: `file_hash`, `file_path`, `file_type`

### Hybrid search (3 modes)
`LocalLens.search()` supports `mode="semantic"`, `mode="keyword"`, or `mode="hybrid"` (default):
- **Semantic:** cosine similarity between query embedding and chunk embeddings
- **Keyword:** BM25 scoring via `locallens/bm25.py` (Rust extension with pure-Python fallback)
- **Hybrid:** both combined via Reciprocal Rank Fusion (RRF, k=60)

### BM25 implementation
`locallens/bm25.py` loads from a Rust extension (`locallens/_rust.py`) or falls back to pure-Python (`locallens/_bm25_core.py`). The Rust crate is built via maturin (see `Cargo.toml`, `src/`). Uses O(N) incremental indexing with running counters.

### Deterministic point IDs and dedup
Point IDs are `uuid5(UUID_NAMESPACE, f"{abs_file_path}:{chunk_index}")` using the namespace `d1b4c5e8-7f3a-4e2b-9a1c-6d8e0f2b3c4a` (identical in both trees, do not change it). Dedup is O(1) per file via a filtered `count` query against the `file_hash` keyword payload index. `--force` bypasses the check.

### Chunking
Structure-aware adaptive chunking in `locallens/chunker.py`:
- **Markdown/text:** split on heading boundaries, then subdivide large sections
- **Code:** split on function/class boundaries (def, class, fn, func)
- **PDF/docx:** split on paragraph boundaries (double newlines)
- **Spreadsheet:** each sheet is one chunk unless >1000 chars

Max chunk 1000 chars, min 100 chars, 50 char overlap. If you change chunk sizes, do it in both `locallens/chunker.py` and `backend/app/services/indexer.py::_chunk_text`.

### Plugin extractors
Extractors are registered via Python entry points (`locallens.extractors` group in `pyproject.toml`). Built-in: text, pdf, docx, code, spreadsheet, liteparse, email, epub, obsidian. Custom extractors extend `locallens.extractors.base.LocalLensExtractor`.

### RAG
Both trees call Ollama's `/api/generate` with `stream: true`. The engine's `ask_stream()` yields `AskStreamEvent` with `event_type="token"` or `"sources"`. System prompt constrains the model to answer only from supplied context.

### Voice pipeline
Voice deps (`moonshine-voice`, `piper-tts`, `sounddevice`, `onnxruntime`) are optional (`locallens[voice]`). STT: Moonshine transcriber. TTS: Piper. Both services expose `is_available()` and routes return HTTP 501 when unavailable. Browser audio (webm/opus) is decoded via `ffmpeg` (must be on PATH).

### Frontend
React 19 + Vite + Tailwind 4 + shadcn/base-ui, routed with `react-router-dom` v7. Pages: `Dashboard`, `IndexPage`, `SearchPage`, `AskPage`, `StackPage`. Voice is merged into `/ask` (mic button + per-message TTS). The backend CORS allow-list is hardcoded to `http://localhost:5173`.

### MCP server
`locallens/mcp_server.py` uses FastMCP. Tools: `locallens_search`, `locallens_ask`, `locallens_index`, `locallens_status`, `locallens_files`. Default port 8811 (SSE transport). Started via `locallens serve --mcp`.

## CI/CD

Four GitHub Actions workflows under `.github/workflows/`:
- **test.yml** — pytest with Qdrant service container, Rust extension build, coverage (Codecov)
- **ci.yml** — ruff check, ruff format, mypy on `locallens/`, `backend/`, `tests/` changes
- **docs.yml** — VitePress build and deploy to GitHub Pages on `docs/**` changes
- **wheels.yml** — cibuildwheel (Linux/macOS-x86/macOS-arm/Windows, abi3-py311), sdist, PyPI publish on release

## Config & Secrets

- `.env` at repo root is read by `backend/app/config.py` (`env_file: "../.env"` relative to `backend/app/`). Do not move it without updating `model_config`.
- Ollama model (`qwen2.5:3b`), embedding model, chunk sizes, and supported extensions live in **two** places (`locallens/config.py` and `backend/app/config.py`). Keep them in sync.
- Key environment variables: `LOCALLENS_DATA_DIR`, `LOCALLENS_COLLECTION`, `LOCALLENS_OLLAMA_URL`, `LOCALLENS_OLLAMA_MODEL`, `LOCALLENS_EMBEDDING_MODEL`, `QDRANT_SYNC_URL`, `QDRANT_SYNC_API_KEY`.

## Build System

The project uses **maturin** as its build backend (not hatchling). The Rust extension (`src/`) provides an optimized BM25 implementation. Python 3.11+ required (abi3-py311). Build with `maturin develop` for local dev or let CI handle wheel builds.

## pyproject.toml extras

| Extra | What it adds |
|---|---|
| `voice` | moonshine-voice, piper-tts, sounddevice, onnxruntime |
| `parsing` | openpyxl, liteparse |
| `ocr` | pytesseract |
| `watch` | watchdog |
| `email` | extract-msg |
| `ebooks` | ebooklib, beautifulsoup4 |
| `mcp` | fastmcp |
| `server` | fastapi, uvicorn, httpx |
| `dev` | ruff, mypy, pre-commit, maturin |
| `all` | everything above |
