from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI IT Support Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    document_storage_path: str = "data/documents"

    chunk_size: int = 1000
    chunk_overlap: int = 200

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "document_chunks"

    openai_api_key: str = ""
    llm_model: str = "gpt-5.6-luna"

    rag_top_k: int = 3
    rag_score_threshold: float = 0.4

    qdrant_timeout_seconds: float = 10.0
    qdrant_max_attempts: int = 3

    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
