from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "locallens"
    vector_size: int = 384
    # Named vector key — must match ``locallens.config.VECTOR_NAME`` on the
    # CLI side so points move between the Edge shard and the server cleanly.
    vector_name: str = "text"

    embedding_model: str = "all-MiniLM-L6-v2"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    chunk_size: int = 500
    chunk_overlap: int = 50
    max_file_size_mb: int = 10
    supported_extensions: str = ".txt,.md,.pdf,.docx,.py,.js,.ts,.go,.rs,.java,.c,.cpp,.rb"

    kokoro_voice: str = "af_heart"
    sample_rate: int = 16000

    model_config = {"env_file": "../.env"}


settings = Settings()
