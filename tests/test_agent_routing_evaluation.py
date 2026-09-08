from ai_it_support_assistant.schemas.agent import (
    AgentDecision,
)
from ai_it_support_assistant.schemas.agent_routing_evaluation import (
    AgentRoutingEvaluationCase,
)
from ai_it_support_assistant.services.agent_routing_evaluation_service import (
    evaluate_case,
)


def test_evaluate_correct_kubernetes_route() -> None:
    case = AgentRoutingEvaluationCase(
        case_id="k8s-test",
        question="How many replicas does demo-api have?",
        expected_action="kubernetes_state",
        expected_kubernetes_resource_type="deployment",
        expected_kubernetes_resource_name="demo-api",
    )

    decision = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="demo-api",
        kubernetes_namespace=None,
        reasoning_summary="Current Deployment state requested.",
    )

    result = evaluate_case(
        case=case,
        decision=decision,
    )

    assert result.action_correct is True
    assert result.arguments_correct is True
    assert result.passed is True


def test_evaluate_wrong_kubernetes_arguments() -> None:
    case = AgentRoutingEvaluationCase(
        case_id="k8s-test",
        question="Is pod demo-worker running?",
        expected_action="kubernetes_state",
        expected_kubernetes_resource_type="pod",
        expected_kubernetes_resource_name="demo-worker",
    )

    decision = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="demo-worker",
        kubernetes_namespace=None,
        reasoning_summary="Current state requested.",
    )

    result = evaluate_case(
        case=case,
        decision=decision,
    )

    assert result.action_correct is True
    assert result.arguments_correct is False
    assert result.passed is False
