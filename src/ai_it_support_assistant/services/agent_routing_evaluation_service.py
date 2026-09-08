from ai_it_support_assistant.schemas.agent import AgentDecision
from ai_it_support_assistant.schemas.agent_routing_evaluation import (
    AgentRoutingEvaluationCase,
    AgentRoutingEvaluationResult,
    AgentRoutingEvaluationSummary,
)


def _arguments_match(
    *,
    case: AgentRoutingEvaluationCase,
    decision: AgentDecision,
) -> bool:
    if decision.action != case.expected_action:
        return False

    if case.expected_action == "rag":
        return (
            decision.service_name is None
            and decision.kubernetes_resource_type is None
            and decision.kubernetes_resource_name is None
            and decision.kubernetes_namespace is None
        )

    if case.expected_action == "live_status":
        return decision.service_name == case.expected_service_name

    if case.expected_action == "kubernetes_state":
        return (
            decision.kubernetes_resource_type == case.expected_kubernetes_resource_type
            and decision.kubernetes_resource_name == case.expected_kubernetes_resource_name
            and decision.kubernetes_namespace == case.expected_kubernetes_namespace
        )

    return False


def evaluate_case(
    *,
    case: AgentRoutingEvaluationCase,
    decision: AgentDecision,
) -> AgentRoutingEvaluationResult:
    action_correct = decision.action == case.expected_action

    arguments_correct = _arguments_match(
        case=case,
        decision=decision,
    )

    return AgentRoutingEvaluationResult(
        case_id=case.case_id,
        question=case.question,
        expected_action=case.expected_action,
        actual_action=decision.action,
        action_correct=action_correct,
        arguments_correct=arguments_correct,
        passed=(action_correct and arguments_correct),
    )


def _accuracy(
    *,
    results: list[AgentRoutingEvaluationResult],
    expected_action: str | None = None,
) -> float:
    selected = results

    if expected_action is not None:
        selected = [result for result in results if result.expected_action == expected_action]

    if not selected:
        return 0.0

    passed = sum(1 for result in selected if result.passed)

    return passed / len(selected)


def build_summary(
    results: list[AgentRoutingEvaluationResult],
) -> AgentRoutingEvaluationSummary:
    total_cases = len(results)

    passed_cases = sum(1 for result in results if result.passed)

    if total_cases:
        routing_accuracy = sum(1 for result in results if result.action_correct) / total_cases

        argument_accuracy = sum(1 for result in results if result.arguments_correct) / total_cases
    else:
        routing_accuracy = 0.0
        argument_accuracy = 0.0

    return AgentRoutingEvaluationSummary(
        total_cases=total_cases,
        passed_cases=passed_cases,
        routing_accuracy=routing_accuracy,
        argument_accuracy=argument_accuracy,
        rag_accuracy=_accuracy(
            results=results,
            expected_action="rag",
        ),
        live_status_accuracy=_accuracy(
            results=results,
            expected_action="live_status",
        ),
        kubernetes_state_accuracy=_accuracy(
            results=results,
            expected_action="kubernetes_state",
        ),
        results=results,
    )
