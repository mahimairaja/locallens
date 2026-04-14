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
    supported_extensions: str = ".txt,.md,.pdf,.docx,.pptx,.xlsx,.xls,.csv,.tsv,.html,.py,.js,.ts,.go,.rs,.java,.c,.cpp,.rb,.eml,.msg,.epub"

    kokoro_voice: str = "af_heart"
    sample_rate: int = 16000

    # Optional API key authentication.  When set, all endpoints require
    # ``Authorization: Bearer <key>`` header.  Unset = open access.
    locallens_api_key: str = ""

    model_config = {"env_file": "../.env"}


settings = Settings()


def collection_for_namespace(namespace: str) -> str:
    """Return the Qdrant collection name for a given namespace.

    The default namespace maps to the original ``locallens`` collection so
    existing data keeps working without migration.
    """
    if namespace == "default":
        return settings.collection_name  # "locallens"
    return f"locallens_{namespace}"
