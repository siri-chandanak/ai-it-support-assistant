import json
from pathlib import Path

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.agent_routing_evaluation import (
    AgentRoutingEvaluationCase,
    AgentRoutingEvaluationResult,
)
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
    route_agent_request,
)
from ai_it_support_assistant.services.agent_routing_evaluation_service import (
    build_summary,
    evaluate_case,
)


def main() -> None:
    settings = get_settings()

    dataset_path = Path("data/evaluation/agent_routing_cases.json")

    raw_cases = json.loads(dataset_path.read_text(encoding="utf-8"))

    cases = [AgentRoutingEvaluationCase.model_validate(item) for item in raw_cases]

    results: list[AgentRoutingEvaluationResult] = []

    for case in cases:
        try:
            decision = route_agent_request(
                question=case.question,
                api_key=settings.openai_api_key,
                model_name=settings.llm_model,
                timeout_seconds=(settings.openai_timeout_seconds),
                max_retries=(settings.openai_max_retries),
            )

            result = evaluate_case(
                case=case,
                decision=decision,
            )

        except AgentRoutingError as exc:
            result = AgentRoutingEvaluationResult(
                case_id=case.case_id,
                question=case.question,
                expected_action=case.expected_action,
                actual_action=None,
                action_correct=False,
                arguments_correct=False,
                passed=False,
                error=str(exc),
            )

        results.append(result)

    summary = build_summary(results)

    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
