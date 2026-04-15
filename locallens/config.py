"""Configuration constants for LocalLens."""

import os
from pathlib import Path

# Qdrant Edge (embedded, on-device)
QDRANT_PATH = Path.home() / ".locallens" / "qdrant_data"
COLLECTION_NAME = "locallens"
# Named vector key — must match the backend's `settings.vector_name`
# so CLI ↔ Docker Qdrant sync produces a compatible schema.
VECTOR_NAME = "text"

# Optional sync to a Qdrant server (enables CLI push-sync during indexing and
# `locallens sync pull` for restoring from a server snapshot). When unset,
# the CLI stays fully offline.
QDRANT_SYNC_URL = os.environ.get("QDRANT_SYNC_URL")
QDRANT_SYNC_API_KEY = os.environ.get("QDRANT_SYNC_API_KEY")

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384
DISTANCE = "Cosine"

# Chunking
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters

# Indexing
MAX_FILE_SIZE_MB = 10
SKIP_HIDDEN = True
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".csv",
    ".tsv",
    ".html",
    ".py",
    ".js",
    ".ts",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".rb",
    ".eml",
    ".msg",
    ".epub",
}

# Ollama (must be running locally: `ollama pull qwen2.5:3b`)
OLLAMA_MODEL = "qwen2.5:3b"
OLLAMA_BASE_URL = "http://localhost:11434"

# Voice
SAMPLE_RATE = 16000
KOKORO_VOICE = "af_heart"
KOKORO_SPEED = 1.0

# Search defaults
DEFAULT_TOP_K = 5
RAG_TOP_K = 3
