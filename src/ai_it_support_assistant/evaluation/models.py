from pydantic import BaseModel, Field


class EvaluationCase(BaseModel):
    case_id: str
    question: str

    should_answer: bool

    expected_document_ids: list[str] = Field(default_factory=list)

    expected_keywords: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    case_id: str
    question: str

    retrieval_hit: bool

    expected_answer_behavior: str
    actual_answer_behavior: str
    behavior_correct: bool

    citation_valid: bool
    keyword_match: bool

    passed: bool


class EvaluationSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int

    pass_rate: float
    retrieval_hit_rate: float
    behavior_accuracy: float
    citation_accuracy: float
    keyword_accuracy: float

    results: list[EvaluationResult]

    embedding_model_name: str
    llm_model: str
    rag_top_k: int
    rag_score_threshold: float

    qdrant_timeout_seconds: float
    qdrant_max_attempts: int
    openai_timeout_seconds: float
    openai_max_retries: int
