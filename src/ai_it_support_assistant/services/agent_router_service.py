import time

from ai_it_support_assistant.observability.metrics import (
    AGENT_DURATION,
    AGENT_ROUTE,
    AGENT_ROUTING_FAILURES,
)
from ai_it_support_assistant.schemas.agent import (
    AgentDecision,
    AgentRoutingOutput,
)
from ai_it_support_assistant.services.llm_service import get_openai_client


class AgentRoutingError(Exception):
    pass


class AgentInputValidationError(AgentRoutingError):
    """Raised when an operational request is missing required input."""

    pass


def validate_agent_decision(
    decision: AgentRoutingOutput,
) -> None:
    if decision.action == "rag":
        if any(
            value is not None
            for value in [
                decision.service_name,
                decision.kubernetes_resource_type,
                decision.kubernetes_resource_name,
                decision.kubernetes_namespace,
                decision.incident_title,
                decision.incident_description,
                decision.incident_severity,
            ]
        ):
            raise AgentRoutingError("rag must not contain tool arguments.")

    elif decision.action == "live_status":
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

        if any(
            value is not None
            for value in [
                decision.incident_title,
                decision.incident_description,
                decision.incident_severity,
            ]
        ):
            raise AgentRoutingError("live_status cannot contain incident arguments.")

    elif decision.action == "kubernetes_state":
        if not decision.kubernetes_resource_type:
            raise AgentRoutingError("kubernetes_state requires resource type.")

        if not decision.kubernetes_resource_name:
            raise AgentRoutingError("kubernetes_state requires resource name.")

        if decision.service_name is not None:
            raise AgentRoutingError("kubernetes_state cannot contain service_name.")

        if any(
            value is not None
            for value in [
                decision.incident_title,
                decision.incident_description,
                decision.incident_severity,
            ]
        ):
            raise AgentRoutingError("kubernetes_state cannot contain incident arguments.")

    elif decision.action == "create_incident":
        if not decision.incident_title:
            raise AgentRoutingError("create_incident requires a title.")

        if not decision.incident_description:
            raise AgentRoutingError("create_incident requires a description.")

        if not decision.incident_severity:
            raise AgentRoutingError("create_incident requires severity.")

        if decision.incident_severity not in {
            "low",
            "medium",
            "high",
            "critical",
        }:
            raise AgentRoutingError("Invalid incident severity.")

        if (
            decision.kubernetes_resource_type is not None
            or decision.kubernetes_resource_name is not None
            or decision.kubernetes_namespace is not None
        ):
            raise AgentRoutingError("create_incident cannot contain Kubernetes arguments.")

        if any(
            value is not None
            for value in [
                decision.kubernetes_resource_type,
                decision.kubernetes_resource_name,
                decision.kubernetes_namespace,
            ]
        ):
            raise AgentRoutingError("create_incident cannot contain Kubernetes arguments.")

    elif decision.action == "restart_deployment":
        if decision.kubernetes_resource_type != "deployment":
            raise AgentRoutingError("restart_deployment only supports deployments.")

        if not decision.kubernetes_resource_name:
            raise AgentRoutingError("restart_deployment requires deployment name.")

        if not decision.kubernetes_namespace:
            raise AgentInputValidationError("restart_deployment requires namespace.")

        if decision.service_name is not None:
            raise AgentRoutingError("restart_deployment cannot include service_name.")

        if any(
            value is not None
            for value in [
                decision.incident_title,
                decision.incident_description,
                decision.incident_severity,
            ]
        ):
            raise AgentRoutingError("restart_deployment cannot include incident arguments.")

    else:
        raise AgentRoutingError(f"Unsupported agent action: {decision.action}")


def route_agent_request(
    *,
    question: str,
    api_key: str,
    model_name: str,
    timeout_seconds: float,
    max_retries: int,
) -> AgentDecision:
    start = time.perf_counter()
    if not question.strip():
        raise AgentRoutingError("Question cannot be empty.")

    instructions = """
You are a routing component for an IT support assistant.

Choose exactly one action.

Always return every field in the response schema.
If a field does not apply to the selected action, return null.
Never omit fields.

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
- incident_title must be null
- incident_description must be null
- incident_severity must be null

2. live_status

Use this only when the user asks about the current operational
health, status, degradation, or availability of a specific service.

Examples:
- Is vpn-gateway healthy right now?
- Is ai-support-api degraded?
- What is the current health of authentication-service?

For live_status:
- extract service_name
- kubernetes_resource_type must be null
- kubernetes_resource_name must be null
- kubernetes_namespace must be null
- incident_title must be null
- incident_description must be null
- incident_severity must be null

3. kubernetes_state

Use this when the user asks for the current state of a specific
Kubernetes resource.

Allowed Kubernetes resource types:
- deployment
- pod

Examples:
- How many replicas does ai-support-api deployment have?
- How many ready replicas does nginx currently have?
- Is pod ai-support-api-123 running?
- What phase is pod api-7fd99 currently in?
- What is the current state of the ai-support-api deployment?

For kubernetes_state:
- extract kubernetes_resource_type
- extract kubernetes_resource_name
- extract kubernetes_namespace only if the user explicitly provides it
- service_name must be null
- incident_title must be null
- incident_description must be null
- incident_severity must be null

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
How many ready replicas does ai-support-api have right now?
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

4. create_incident

Use this only when the user explicitly asks to create, open, or file
an incident or ticket.

Examples:
- Create an incident for vpn-gateway.
- Open a ticket for ai-support-api being unavailable.
- File an incident because authentication-service is failing.

For create_incident:
- extract or draft a concise incident title
- draft a factual incident description
- choose severity only from:
  low, medium, high, critical
- include service_name when clearly identified
- kubernetes_resource_type must be null
- kubernetes_resource_name must be null
- kubernetes_namespace must be null

Do not claim the incident has been created.
The application requires explicit approval before execution.

Rules:
- Do not execute anything.
- Do not invent service names.
- Do not invent Kubernetes resource names.
- Do not invent Kubernetes namespaces.
- Never choose Kubernetes credentials, kubeconfig, cluster context,
  API server, ServiceAccount, or authentication information.
- Only choose create_incident when the user explicitly asks to
  create, open, or file an incident or ticket.
- If the question only asks how to troubleshoot something, use rag.
- If the question only asks for current service health, use live_status.
- If the question asks for current Kubernetes resource state,
  use kubernetes_state.
- If the question is ambiguous and does not clearly require live data
  or a write action, prefer rag.
- Keep reasoning_summary short.

5. restart_deployment

Use this action only when the user explicitly asks to restart
or roll out a specific Kubernetes Deployment.

Requirements:
- kubernetes_resource_type must be "deployment"
- extract the exact Deployment name
- extract an explicit Kubernetes namespace
- if namespace is not provided, do NOT invent one
- service_name must be null
- incident fields must be null
- do not execute anything
- do not claim the restart happened
- the application requires explicit approval before execution

Important routing distinction:

A question asking HOW to restart a Kubernetes Deployment is a
documentation question and should use "rag".

A question asking for current Deployment state should use
"kubernetes_state".

An explicit request to actually restart a Deployment should use
"restart_deployment".
""".strip()

    try:
        client = get_openai_client(
            api_key,
            timeout_seconds,
            max_retries,
        )

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
                        "schema": AgentRoutingOutput.model_json_schema(),
                    }
                },
            )
        except Exception as exc:
            raise AgentRoutingError("Agent routing failed.") from exc

        try:
            routing_output = AgentRoutingOutput.model_validate_json(response.output_text)
        except Exception as exc:
            raise AgentRoutingError("Agent returned invalid routing output.") from exc

        validate_agent_decision(routing_output)

        decision = AgentDecision.model_validate(routing_output.model_dump())

        AGENT_ROUTE.labels(
            action=decision.action,
        ).inc()

        return decision

    except AgentRoutingError:
        # Includes:
        # - OpenAI routing failure
        # - invalid structured output
        # - invalid routing arguments
        AGENT_ROUTING_FAILURES.inc()
        raise

    except Exception as exc:
        # Defensive catch for unexpected routing failures.
        AGENT_ROUTING_FAILURES.inc()

        raise AgentRoutingError("Unexpected agent routing failure.") from exc

    finally:
        AGENT_DURATION.observe(time.perf_counter() - start)
