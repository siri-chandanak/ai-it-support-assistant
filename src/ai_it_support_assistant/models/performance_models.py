from pydantic import BaseModel, Field


class PerformanceBaseline(BaseModel):
    git_sha: str
    environment: str

    concurrency: int = Field(ge=0)

    request_count: int = Field(ge=0)

    error_rate: float = Field(
        ge=0.0,
        le=1.0,
    )

    p50_ms: float = Field(ge=0.0)

    p95_ms: float = Field(ge=0.0)

    p99_ms: float = Field(ge=0.0)

    throughput_per_second: float = Field(ge=0.0)


class ScenarioPerformanceBaseline(PerformanceBaseline):
    scenario: str

    cache_hit_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    average_input_tokens: float | None = Field(
        default=None,
        ge=0.0,
    )

    average_output_tokens: float | None = Field(
        default=None,
        ge=0.0,
    )

    estimated_cost_per_request: float | None = Field(
        default=None,
        ge=0.0,
    )


class PerformanceConfiguration(BaseModel):
    git_sha: str
    environment: str

    embedding_model_name: str
    llm_model: str

    rag_top_k: int
    rag_score_threshold: float

    qdrant_collection_name: str

    cache_enabled: bool | None = None

    api_replicas: int | None = Field(
        default=None,
        ge=0,
    )

    worker_replicas: int | None = Field(
        default=None,
        ge=0,
    )

    pdp_mode: str | None = None


class PerformanceReport(BaseModel):
    configuration: PerformanceConfiguration

    scenarios: list[ScenarioPerformanceBaseline] = Field(
        default_factory=list,
    )

    qdrant_p95_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    embedding_queries_per_second: float | None = Field(
        default=None,
        ge=0.0,
    )

    http_error_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    opa_p95_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    rag_p95_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    average_input_tokens: float | None = Field(
        default=None,
        ge=0.0,
    )

    average_output_tokens: float | None = Field(
        default=None,
        ge=0.0,
    )

    estimated_cost_per_rag_answer: float | None = Field(
        default=None,
        ge=0.0,
    )

    cache_hit_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    worker_queue_p95_ms: float | None = Field(
        default=None,
        ge=0.0,
    )

    generated_at_utc: str
