from ai_it_support_assistant.schemas.agent import AgentDecision
from ai_it_support_assistant.services.llm_service import get_openai_client


class AgentRoutingError(Exception):
    pass


def validate_agent_decision(
    decision: AgentDecision,
) -> None:
    if decision.action == "live_status" and not decision.service_name:
        raise AgentRoutingError("live_status requires a service name.")

    if decision.action == "rag" and decision.service_name is not None:
        raise AgentRoutingError("rag must not include a service name.")


def route_agent_request(
    *,
    question: str,
    api_key: str,
    model_name: str,
    timeout_seconds: float,
    max_retries: int,
) -> AgentDecision:
    if not question.strip():
        raise AgentRoutingError("Question cannot be empty.")

    client = get_openai_client(
        api_key,
        timeout_seconds,
        max_retries,
    )

    instructions = """
You are a routing component for an IT support assistant.

Choose exactly one action.

Available actions:

1. rag
Use this when the user asks about documented procedures,
policies, troubleshooting instructions, runbooks, or
historical company knowledge.

2. live_status
Use this only when the user asks for the current or live
health/status/availability of a specific service.

Rules:
- Do not execute anything.
- Do not invent service names.
- For live_status, extract the service name from the user's question.
- For rag, service_name must be null.
- If the question is ambiguous, prefer rag.
- Keep reasoning_summary short.
""".strip()

    try:
        response = client.responses.create(
            model=model_name,
            instructions=instructions,
            input=question,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "agent_decision",
                    "strict": True,
                    "schema": AgentDecision.model_json_schema(),
                }
            },
        )
    except Exception as exc:
        raise AgentRoutingError("Agent routing failed.") from exc

    try:
        decision = AgentDecision.model_validate_json(response.output_text)
    except Exception as exc:
        raise AgentRoutingError("Agent returned invalid routing output.") from exc

    validate_agent_decision(decision)

    return decision
