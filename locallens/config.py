"""Configuration constants for LocalLens."""

from pathlib import Path

# Qdrant
QDRANT_PATH = Path.home() / ".locallens" / "qdrant_data"
COLLECTION_NAME = "locallens"

# Embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
VECTOR_SIZE = 384
DISTANCE = "Cosine"

# Chunking
CHUNK_SIZE = 500          # characters
CHUNK_OVERLAP = 50        # characters

# Indexing
MAX_FILE_SIZE_MB = 10
SKIP_HIDDEN = True
SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx",
    ".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb",
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
