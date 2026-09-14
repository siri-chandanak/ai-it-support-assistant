import logging

from sqlalchemy.orm import Session

from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.schemas.agent import (
    AgentResponse,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.action_proposal_service import (
    prepare_incident_action,
    prepare_restart_action,
)
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
    route_agent_request,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    get_kubernetes_resource_state,
)
from ai_it_support_assistant.services.live_status_service import (
    get_live_service_status,
)
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)
from ai_it_support_assistant.services.resource_authorization_service import (
    require_namespace_permission,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    authorize_tool,
)

logger = logging.getLogger(__name__)


def handle_agent_request(
    *,
    question: str,
    current_user: User,
    session: Session,
    embedding_model_name: str,
    qdrant_url: str,
    collection_name: str,
    qdrant_timeout_seconds: float,
    qdrant_max_attempts: int,
    rag_top_k: int,
    rag_score_threshold: float,
    openai_api_key: str,
    llm_model: str,
    openai_timeout_seconds: float,
    openai_max_retries: int,
    kubernetes_config_mode: str,
    kubernetes_context: str,
    kubernetes_default_namespace: str,
    kubernetes_write_enabled: bool,
    kubernetes_restart_allowed_namespaces: str,
    kubernetes_restart_allowed_deployments: str,
    embedding_cache_enabled: bool,
    retrieval_cache_enabled: bool,
) -> AgentResponse:
    decision = route_agent_request(
        question=question,
        api_key=openai_api_key,
        model_name=llm_model,
        timeout_seconds=openai_timeout_seconds,
        max_retries=openai_max_retries,
    )

    logger.info(
        "agent_decision request_id=%s action=%s",
        get_request_id(),
        decision.action,
    )

    if decision.action == "rag":
        rag_response = answer_question(
            question=question,
            top_k=rag_top_k,
            score_threshold=rag_score_threshold,
            embedding_model_name=embedding_model_name,
            qdrant_url=qdrant_url,
            collection_name=collection_name,
            qdrant_timeout_seconds=qdrant_timeout_seconds,
            qdrant_max_attempts=qdrant_max_attempts,
            openai_api_key=openai_api_key,
            llm_model=llm_model,
            openai_timeout_seconds=openai_timeout_seconds,
            openai_max_retries=openai_max_retries,
            embedding_cache_enabled=embedding_cache_enabled,
            retrieval_cache_enabled=retrieval_cache_enabled,
            user_roles=current_user.roles,
        )

        return AgentResponse(
            question=question,
            action="rag",
            answer=rag_response.answer,
        )

    if decision.action == "live_status":
        authorize_tool(
            tool_name="live_status",
            user=current_user,
        )

        if decision.service_name is None:
            raise AgentRoutingError("Missing service name.")

        logger.info(
            "tool_execution_started request_id=%s tool=live_status",
            get_request_id(),
        )

        service_status = get_live_service_status(
            service_name=decision.service_name,
        )

        logger.info(
            ("tool_execution_completed request_id=%s tool=live_status status=%s"),
            get_request_id(),
            service_status.status,
        )

        answer = (
            f"{service_status.service_name} is {service_status.status}. {service_status.message}"
        )

        return AgentResponse(
            question=question,
            action="live_status",
            answer=answer,
        )

    if decision.action == "kubernetes_state":
        authorize_tool(
            tool_name="kubernetes_state",
            user=current_user,
        )

        if decision.kubernetes_resource_type is None or decision.kubernetes_resource_name is None:
            raise AgentRoutingError("Missing Kubernetes arguments.")

        namespace = decision.kubernetes_namespace or kubernetes_default_namespace

        require_namespace_permission(
            user=current_user,
            permission="kubernetes:read",
            namespace=namespace,
            session=session,
        )

        logger.info(
            (
                "tool_execution_started "
                "request_id=%s "
                "tool=kubernetes_state "
                "resource_type=%s "
                "namespace=%s"
            ),
            get_request_id(),
            decision.kubernetes_resource_type,
            namespace,
        )

        state = get_kubernetes_resource_state(
            resource_type=decision.kubernetes_resource_type,
            name=decision.kubernetes_resource_name,
            namespace=namespace,
            config_mode=kubernetes_config_mode,
            context=kubernetes_context,
        )

        logger.info(
            ("tool_execution_completed request_id=%s tool=kubernetes_state resource_type=%s"),
            get_request_id(),
            state.resource_type,
        )

        if state.resource_type == "deployment":
            answer = (
                f"Deployment {state.name} in namespace "
                f"{state.namespace} has "
                f"{state.ready_replicas}/"
                f"{state.desired_replicas} ready replicas "
                f"and {state.available_replicas} "
                f"available replicas."
            )
        else:
            answer = (
                f"Pod {state.name} in namespace "
                f"{state.namespace} is in phase "
                f"{state.phase}. "
                f"Ready={state.ready}. "
                f"Restart count={state.restart_count}."
            )

        return AgentResponse(
            question=question,
            action="kubernetes_state",
            answer=answer,
        )

    if decision.action == "create_incident":
        authorize_tool(
            tool_name="create_incident",
            user=current_user,
        )

        evidence_text = "No live service evidence was available."

        if decision.service_name:
            service_status = get_live_service_status(
                service_name=decision.service_name,
            )

            evidence_text = (
                f"Current service status: {service_status.status}. {service_status.message}"
            )

        incident_request = IncidentCreateRequest(
            title=decision.incident_title,
            description=(f"{decision.incident_description}\n\nEvidence:\n{evidence_text}"),
            severity=decision.incident_severity,
            service_name=decision.service_name,
        )

        pending = prepare_incident_action(
            session=session,
            current_user=current_user,
            request=incident_request,
        )

        session.commit()

        return AgentResponse(
            question=question,
            action="create_incident",
            answer=("Incident creation requires explicit approval."),
            approval_required=True,
            approval_id=pending.approval_id,
            proposed_incident=incident_request,
            incident_id=None,
        )

    if decision.action == "restart_deployment":
        deployment_name = decision.kubernetes_resource_name
        namespace = decision.kubernetes_namespace

        # Write operations must explicitly specify
        # the target Deployment and namespace.
        if deployment_name is None:
            raise AgentRoutingError("Deployment name is required.")

        if namespace is None:
            raise AgentRoutingError("Namespace is required for restart_deployment.")

        logger.info(
            ("restart_proposal_started request_id=%s namespace=%s deployment=%s"),
            get_request_id(),
            namespace,
            deployment_name,
        )

        pending, restart_payload = prepare_restart_action(
            session=session,
            current_user=current_user,
            deployment_name=deployment_name,
            namespace=namespace,
            kubernetes_write_enabled=(kubernetes_write_enabled),
            kubernetes_restart_allowed_namespaces=(kubernetes_restart_allowed_namespaces),
            kubernetes_restart_allowed_deployments=(kubernetes_restart_allowed_deployments),
            kubernetes_config_mode=(kubernetes_config_mode),
            kubernetes_context=(kubernetes_context),
        )

        session.commit()

        logger.info(
            ("restart_proposal_created request_id=%s approval_id=%s namespace=%s deployment=%s"),
            get_request_id(),
            pending.approval_id,
            restart_payload.namespace,
            restart_payload.name,
        )

        return AgentResponse(
            question=question,
            action="restart_deployment",
            answer=("Deployment restart requires explicit approval."),
            approval_required=True,
            approval_id=pending.approval_id,
            proposed_restart=restart_payload,
        )

    raise AgentRoutingError("Unsupported agent action.")
