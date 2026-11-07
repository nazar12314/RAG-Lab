from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://raglab:raglab@localhost:5432/raglab"

    openai_api_key: SecretStr | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    dataset_version: str = "engineering-ops-v1"
    default_top_k: int = Field(default=5, ge=1)
    default_graph_hops: int = Field(default=2, ge=1, le=3)

    backend_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
