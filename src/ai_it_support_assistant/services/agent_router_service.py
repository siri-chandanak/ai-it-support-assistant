from ai_it_support_assistant.schemas.agent import AgentDecision
from ai_it_support_assistant.services.llm_service import get_openai_client


class AgentRoutingError(Exception):
    pass


def validate_agent_decision(
    decision: AgentDecision,
) -> None:
    if decision.action == "rag":
        if any(
            value is not None
            for value in [
                decision.service_name,
                decision.kubernetes_resource_type,
                decision.kubernetes_resource_name,
                decision.kubernetes_namespace,
            ]
        ):
            raise AgentRoutingError("rag must not contain tool arguments.")

    if decision.action == "live_status":
        if not decision.service_name:
            raise AgentRoutingError("live_status requires a service name.")

        if any(
            value is not None
            for value in [
                decision.kubernetes_resource_type,
                decision.kubernetes_resource_name,
                decision.kubernetes_namespace,
            ]
        ):
            raise AgentRoutingError("live_status cannot contain Kubernetes arguments.")

    if decision.action == "kubernetes_state":
        if not decision.kubernetes_resource_type:
            raise AgentRoutingError("kubernetes_state requires resource type.")

        if not decision.kubernetes_resource_name:
            raise AgentRoutingError("kubernetes_state requires resource name.")

        if decision.service_name is not None:
            raise AgentRoutingError("kubernetes_state cannot contain service_name.")


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

Use this when the user asks about:
- documented procedures
- troubleshooting instructions
- policies
- runbooks
- explanations
- historical company knowledge
- how to perform or diagnose something

Examples:
- How do I troubleshoot a pod that keeps restarting?
- What does CrashLoopBackOff mean?
- What is the documented escalation process for MFA failures?

For rag:
- service_name must be null
- kubernetes_resource_type must be null
- kubernetes_resource_name must be null
- kubernetes_namespace must be null


2. live_status

Use this only when the user asks about the current operational
health, status, degradation, or availability of a specific service.

Examples:
- Is vpn-gateway healthy right now?
- Is payment-api degraded?
- What is the current health of authentication-service?

For live_status:
- extract service_name
- kubernetes_resource_type must be null
- kubernetes_resource_name must be null
- kubernetes_namespace must be null


3. kubernetes_state

Use this when the user asks for the current state of a specific
Kubernetes resource.

Allowed Kubernetes resource types:
- deployment
- pod

Examples:
- How many replicas does payment-api deployment have?
- How many ready replicas does nginx currently have?
- Is pod payment-api-123 running?
- What phase is pod api-7fd99 currently in?
- What is the current state of the payment-api deployment?

For kubernetes_state:
- extract kubernetes_resource_type
- extract kubernetes_resource_name
- extract kubernetes_namespace only if the user explicitly provides it
- service_name must be null

Important routing distinction:

Use live_status for application or service health questions such as:
- healthy
- unhealthy
- degraded
- available
- unavailable

Use kubernetes_state when the user explicitly asks about Kubernetes
resource state such as:
- deployment
- pod
- replicas
- ready replicas
- restart count
- phase
- namespace

Examples of the distinction:

Question:
How do I check whether a Deployment has enough ready replicas?
Action:
rag

Question:
How many ready replicas does payment-api have right now?
Action:
kubernetes_state

Question:
What does degraded service health mean?
Action:
rag

Question:
Is vpn-gateway degraded right now?
Action:
live_status

Rules:
- Do not execute anything.
- Do not invent service names.
- Do not invent Kubernetes resource names.
- Do not invent Kubernetes namespaces.
- Never choose Kubernetes credentials, kubeconfig, cluster context,
  API server, ServiceAccount, or authentication information.
- If the question is ambiguous and does not clearly require live data,
  prefer rag.
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
