"""Application settings.

A single, typed settings object is the seam that keeps the rest of the code
provider-agnostic: swap the LLM model or embedding model here (or via env) and
nothing else changes. Values are read from environment variables / a local
`.env` file via pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ---- LLM (Groq by default) ----
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_eval_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024

    # ---- Embeddings (local sentence-transformers) ----
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ---- Postgres ----
    postgres_user: str = "docvault"
    postgres_password: str = "docvault"
    postgres_db: str = "docvault"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    # Explicit override wins over the assembled URL (handy on PaaS providers).
    database_url: str | None = None

    # ---- Redis ----
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: str | None = None

    # ---- RAG tuning ----
    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_top_k: int = 4
    vector_index_type: str = "hnsw"  # "hnsw" | "ivfflat"

    # ---- Semantic cache ----
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.92
    semantic_cache_ttl_seconds: int = 86_400
    semantic_cache_max_entries: int = 1000

    # ---- Rate limiting ----
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_query: str = "20/minute"

    # ---- Cost accounting (USD per 1M tokens) ----
    cost_per_1m_input_tokens: float = 0.59
    cost_per_1m_output_tokens: float = 0.79

    # ---- Uploads ----
    max_upload_mb: int = 20
    upload_dir: str = "./uploads"

    allowed_content_types: tuple[str, ...] = Field(
        default=(
            "application/pdf",
            "text/plain",
            "text/markdown",
            "text/x-markdown",
            "application/octet-stream",  # some clients send .md/.txt as this
        ),
    )

    # ---- Derived values ----
    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            # Normalise common `postgres://` / sync URLs to the async driver.
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_dsn(self) -> str:
        return self.redis_url or f"redis://{self.redis_host}:{self.redis_port}/0"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()


settings = get_settings()
