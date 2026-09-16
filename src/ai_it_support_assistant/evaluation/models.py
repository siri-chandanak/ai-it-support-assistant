from pydantic import BaseModel, Field

from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyResource,
    PolicySubject,
)


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


class AuthorizationEvaluationCase(BaseModel):
    case_id: str
    question: str

    user_roles: list[str] = Field(
        min_length=1,
    )

    expected_allowed_document_ids: list[str] = Field(
        default_factory=list,
    )

    forbidden_document_ids: list[str] = Field(
        default_factory=list,
    )

    forbidden_text_fragments: list[str] = Field(
        default_factory=list,
    )

    should_answer: bool


class AuthorizationEvaluationResult(BaseModel):
    case_id: str
    question: str
    user_roles: list[str]

    authorized_retrieval_hit: bool

    unauthorized_document_leak: bool
    unauthorized_text_leak: bool
    citation_leak: bool

    expected_behavior: str
    actual_behavior: str
    behavior_correct: bool

    passed: bool


class AuthorizationEvaluationSummary(BaseModel):
    total_cases: int

    passed_cases: int
    failed_cases: int

    pass_rate: float

    unauthorized_document_leak_count: int
    unauthorized_text_leak_count: int
    citation_leak_count: int

    authorized_retrieval_rate: float
    behavior_accuracy: float

    results: list[AuthorizationEvaluationResult]


class PolicyEvaluationCase(BaseModel):
    case_id: str
    description: str

    subject: PolicySubject
    action: str
    resource: PolicyResource

    context: PolicyContext = Field(default_factory=PolicyContext)

    expected_allowed: bool
    expected_reason_code: str | None = None


class PolicyEvaluationResult(BaseModel):
    case_id: str
    description: str

    expected_allowed: bool
    actual_allowed: bool

    expected_reason_code: str | None = None
    actual_reason_code: str

    policy_id: str

    decision_correct: bool
    reason_correct: bool

    false_allow: bool
    false_deny: bool

    passed: bool


class PolicyEvaluationSummary(BaseModel):
    total_cases: int

    passed_cases: int
    failed_cases: int

    pass_rate: float

    expected_allows: int
    expected_denies: int

    false_allows: int
    false_denies: int

    allow_accuracy: float
    deny_accuracy: float

    results: list[PolicyEvaluationResult]
