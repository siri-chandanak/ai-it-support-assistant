from pydantic import BaseModel

from ai_it_support_assistant.schemas.agent import AgentAction


class AgentRoutingEvaluationCase(BaseModel):
    case_id: str
    question: str

    expected_action: AgentAction

    expected_service_name: str | None = None

    expected_kubernetes_resource_type: str | None = None
    expected_kubernetes_resource_name: str | None = None
    expected_kubernetes_namespace: str | None = None


class AgentRoutingEvaluationResult(BaseModel):
    case_id: str
    question: str

    expected_action: AgentAction
    actual_action: AgentAction | None

    action_correct: bool
    arguments_correct: bool
    passed: bool

    error: str | None = None


class AgentRoutingEvaluationSummary(BaseModel):
    total_cases: int
    passed_cases: int

    routing_accuracy: float
    argument_accuracy: float

    rag_accuracy: float
    live_status_accuracy: float
    kubernetes_state_accuracy: float

    results: list[AgentRoutingEvaluationResult]
