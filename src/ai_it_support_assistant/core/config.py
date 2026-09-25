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

    embedding_cache_enabled: bool = True
    embedding_cache_ttl_seconds: int = 3600
    embedding_cache_max_size: int = 1000

    retrieval_cache_enabled: bool = True
    retrieval_cache_ttl_seconds: int = 300
    retrieval_cache_max_size: int = 1000

    database_url: str = (
        "postgresql+psycopg://ai_support:ai_support_local_password@localhost:5432/ai_support"
    )

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    kubernetes_config_mode: str = "local"
    kubernetes_context: str = ""
    kubernetes_default_namespace: str = "ai-it-support-test"

    kubernetes_write_enabled: bool = False
    kubernetes_restart_allowed_namespaces: str = "dev,development"
    kubernetes_restart_allowed_deployments: str = ""

    kubernetes_rollout_timeout_seconds: int = 120
    kubernetes_rollout_poll_interval_seconds: int = 5
    kubernetes_rollout_max_read_failures: int = 3

    action_worker_enabled: bool = False
    action_worker_poll_interval_seconds: float = 2.0
    action_worker_batch_size: int = 5
    action_worker_stale_after_seconds: int = 300

    mcp_enabled: bool = False
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001

    mcp_issuer_url: str = "http://127.0.0.1:8000"

    mcp_resource_server_url: str = "http://127.0.0.1:8001/mcp"

    auth_mode: str = "demo"

    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_algorithms: str = "RS256"

    oidc_required_scope: str = "ai-support.access"

    policy_pdp_mode: str = "local"

    opa_url: str = "http://127.0.0.1:8181"
    opa_policy_path: str = "ai_it_support/authz/decision"
    opa_timeout_seconds: float = 2.0
    opa_max_attempts: int = 2
    opa_health_check_enabled: bool = True

    policy_shadow_pdp_enabled: bool = False

    opa_bundle_enabled: bool = False
    opa_bundle_name: str = "ai-it-support-authz"
    opa_require_bundle_ready: bool = True

    policy_input_version: str = "1"

    otel_enabled: bool = False
    otel_service_name: str = "ai-it-support-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_environment: str = "development"

    metrics_enabled: bool = True
    worker_metrics_port: int = 9101

    e2e_enabled: bool = False
    e2e_kubernetes_writes_enabled: bool = False
    e2e_expected_environment: str = "development"
    e2e_test_namespace: str = ""
    e2e_test_deployment: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def oidc_algorithm_list(self) -> list[str]:
        return [
            algorithm.strip() for algorithm in self.oidc_algorithms.split(",") if algorithm.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
