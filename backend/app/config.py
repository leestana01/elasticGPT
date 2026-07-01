from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables (.env)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- AI Provider ----
    ai_provider: str = "mock"  # mock | openai
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4.1-mini"
    # Fixed vector dimension used by the Elasticsearch mapping. The mock provider
    # produces vectors of exactly this size so the index works regardless of provider.
    embedding_dim: int = 1536

    # ---- Kafka ----
    kafka_bootstrap_servers: str = "kafka:9092"
    consumer_group_prefix: str = "elasticgpt"

    # ---- Elasticsearch ----
    elasticsearch_url: str = "http://elasticsearch:9200"
    index_prefix: str = "rag"

    # ---- PostgreSQL ----
    database_url: str = "postgresql+psycopg2://elasticgpt:elasticgpt@postgres:5432/elasticgpt"

    # ---- Redis ----
    redis_url: str = "redis://redis:6379/0"

    # ---- Vault ----
    vault_root: str = "/vault"
    default_vault_id: str = "vault_sample_001"
    default_vault_name: str = "sample"
    default_user_id: str = "user_001"
    auto_register_sample_vault: bool = True

    # ---- Chunking ----
    chunk_min_tokens: int = 500
    chunk_max_tokens: int = 1000
    chunk_overlap_tokens: int = 120

    # ---- Retrieval / Generation ----
    default_top_k: int = 8
    candidate_pool: int = 50
    context_token_limit: int = 3000
    graph_depth: int = 1
    linked_note_chunk_limit: int = 2
    incoming_link_boost: float = 0.2
    outgoing_link_boost: float = 0.3
    same_folder_boost: float = 0.1
    same_tag_boost: float = 0.2

    # ---- Reliability ----
    max_local_retries: int = 3
    retry_backoff_base: float = 0.5

    # ---- Worker ----
    worker_type: str = "parser"
    heartbeat_file: str = "/tmp/worker_healthy"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
