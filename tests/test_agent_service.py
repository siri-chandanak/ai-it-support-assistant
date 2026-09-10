from unittest.mock import Mock, patch
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    IncidentModel,
    PendingIncidentActionModel,
)
from ai_it_support_assistant.schemas.agent import (
    AgentDecision,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentState,
    PodState,
)
from ai_it_support_assistant.schemas.rag import RAGResponse
from ai_it_support_assistant.schemas.tools import (
    ServiceStatus,
)
from ai_it_support_assistant.services.agent_service import (
    handle_agent_request,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    ToolAuthorizationError,
)


def _agent_kwargs() -> dict[str, object]:
    return {
        "embedding_model_name": "test-embedding-model",
        "qdrant_url": "http://test-qdrant",
        "collection_name": "test-collection",
        "qdrant_timeout_seconds": 5.0,
        "qdrant_max_attempts": 1,
        "rag_top_k": 3,
        "rag_score_threshold": 0.5,
        "openai_api_key": "test-key",
        "llm_model": "test-model",
        "openai_timeout_seconds": 5.0,
        "openai_max_retries": 1,
        "embedding_cache_enabled": False,
        "retrieval_cache_enabled": False,
        "kubernetes_config_mode": "local",
        "kubernetes_context": "kind-kin",
        "kubernetes_default_namespace": "ai-it-support-test",
    }


def call_agent(
    *,
    current_user: User,
    question: str,
    session: Session,
):
    return handle_agent_request(
        question=question,
        current_user=current_user,
        session=session,
        **_agent_kwargs(),
    )


def test_agent_executes_only_rag_path(db_session: Session) -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        username="reader",
        roles=["reader"],
    )

    decision = AgentDecision(
        action="rag",
        service_name=None,
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        reasoning_summary="Documentation question.",
    )

    rag_response = RAGResponse(
        question="How do I troubleshoot VPN?",
        answer="Restart the VPN client.",
        sources=[],
        retrieved_chunks=[],
        insufficient_context=False,
    )

    with (
        patch(
            "ai_it_support_assistant.services.agent_service.route_agent_request",
            return_value=decision,
        ),
        patch(
            "ai_it_support_assistant.services.agent_service.answer_question",
            return_value=rag_response,
        ) as mock_rag,
        patch(
            "ai_it_support_assistant.services.agent_service.get_live_service_status"
        ) as mock_live,
    ):
        result = handle_agent_request(
            question="How do I troubleshoot VPN?",
            current_user=user,
            session=db_session,
            **_agent_kwargs(),
        )

    assert result.action == "rag"
    assert result.answer == "Restart the VPN client."

    mock_rag.assert_called_once()
    mock_live.assert_not_called()


def test_agent_executes_only_live_status_path(db_session: Session) -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        username="support",
        roles=["it_support"],
    )

    decision = AgentDecision(
        action="live_status",
        service_name="vpn-gateway",
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        reasoning_summary="Live status question.",
    )

    service_status = ServiceStatus(
        service_name="vpn-gateway",
        status="degraded",
        message="Authentication latency is elevated.",
    )

    with (
        patch(
            "ai_it_support_assistant.services.agent_service.route_agent_request",
            return_value=decision,
        ),
        patch("ai_it_support_assistant.services.agent_service.answer_question") as mock_rag,
        patch(
            "ai_it_support_assistant.services.agent_service.get_live_service_status",
            return_value=service_status,
        ) as mock_live,
    ):
        result = handle_agent_request(
            question="Is vpn-gateway healthy right now?",
            current_user=user,
            session=db_session,
            **_agent_kwargs(),
        )

    assert result.action == "live_status"
    assert "vpn-gateway is degraded" in result.answer

    mock_live.assert_called_once()
    mock_rag.assert_not_called()


def test_authorization_happens_before_live_tool_execution(db_session: Session) -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        username="reader",
        roles=["reader"],
    )

    decision = AgentDecision(
        action="live_status",
        service_name="vpn-gateway",
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        reasoning_summary="Live status question.",
    )

    with (
        patch(
            "ai_it_support_assistant.services.agent_service.route_agent_request",
            return_value=decision,
        ),
        patch(
            "ai_it_support_assistant.services.agent_service.get_live_service_status"
        ) as mock_live,
    ):
        with pytest.raises(ToolAuthorizationError):
            handle_agent_request(
                question="Is vpn-gateway healthy right now?",
                current_user=user,
                session=db_session,
                **_agent_kwargs(),
            )

    mock_live.assert_not_called()


@patch("ai_it_support_assistant.services.agent_service.get_kubernetes_resource_state")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_reader_is_denied_before_kubernetes_call(
    mock_route_agent_request: Mock,
    mock_kubernetes_tool: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="demo-api",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary=("The user asks for current Deployment state."),
    )

    reader = User(
        user_id=UUID("00000000-0000-0000-0000-000000000004"),
        username="reader",
        roles=["reader"],
    )

    with pytest.raises(ToolAuthorizationError):
        call_agent(
            current_user=reader,
            question=("How many replicas does demo-api have in ai-it-support-test?"),
            session=db_session,
        )

    mock_kubernetes_tool.assert_not_called()


@patch("ai_it_support_assistant.services.agent_service.get_kubernetes_resource_state")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_it_support_can_read_deployment_state(
    mock_route_agent_request: Mock,
    mock_kubernetes_tool: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="demo-api",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary=("The user asks for current Deployment state."),
    )

    mock_kubernetes_tool.return_value = DeploymentState(
        name="demo-api",
        namespace="ai-it-support-test",
        desired_replicas=2,
        ready_replicas=2,
        available_replicas=2,
        updated_replicas=2,
    )

    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000005"),
        username="support",
        roles=["it_support"],
    )

    response = call_agent(
        current_user=support_user,
        question=("How many ready replicas does demo-api have in ai-it-support-test?"),
        session=db_session,
    )

    assert response.action == "kubernetes_state"
    assert "demo-api" in response.answer
    assert "2/2" in response.answer

    mock_kubernetes_tool.assert_called_once_with(
        resource_type="deployment",
        name="demo-api",
        namespace="ai-it-support-test",
        config_mode="local",
        context="kind-kin",
    )


@patch("ai_it_support_assistant.services.agent_service.get_kubernetes_resource_state")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_it_support_can_read_pod_state(
    mock_route_agent_request: Mock,
    mock_kubernetes_tool: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="pod",
        kubernetes_resource_name="demo-worker",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary=("The user asks for current Pod state."),
    )

    mock_kubernetes_tool.return_value = PodState(
        name="demo-worker",
        namespace="ai-it-support-test",
        phase="Running",
        ready=True,
        restart_count=0,
    )

    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000006"),
        username="support",
        roles=["it_support"],
    )

    response = call_agent(
        current_user=support_user,
        question=("Is pod demo-worker running in ai-it-support-test?"),
        session=db_session,
    )

    assert response.action == "kubernetes_state"
    assert "demo-worker" in response.answer
    assert "Running" in response.answer
    assert "Ready=True" in response.answer
    assert "Restart count=0" in response.answer

    mock_kubernetes_tool.assert_called_once_with(
        resource_type="pod",
        name="demo-worker",
        namespace="ai-it-support-test",
        config_mode="local",
        context="kind-kin",
    )


@patch("ai_it_support_assistant.services.agent_service.get_kubernetes_resource_state")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_kubernetes_uses_default_namespace_when_missing(
    mock_route_agent_request: Mock,
    mock_kubernetes_tool: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="demo-api",
        kubernetes_namespace=None,
        reasoning_summary=("The user asks for current Deployment state."),
    )

    mock_kubernetes_tool.return_value = DeploymentState(
        name="demo-api",
        namespace="ai-it-support-test",
        desired_replicas=2,
        ready_replicas=2,
        available_replicas=2,
        updated_replicas=2,
    )

    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000007"),
        username="support",
        roles=["it_support"],
    )

    response = call_agent(
        current_user=support_user,
        question="How many replicas does demo-api have?",
        session=db_session,
    )

    assert response.action == "kubernetes_state"

    mock_kubernetes_tool.assert_called_once_with(
        resource_type="deployment",
        name="demo-api",
        namespace="ai-it-support-test",
        config_mode="local",
        context="kind-kin",
    )


@patch("ai_it_support_assistant.services.agent_service.get_live_service_status")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_it_support_can_propose_incident_without_executing_write(
    mock_route_agent_request: Mock,
    mock_live_status: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="create_incident",
        service_name="vpn-gateway",
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        incident_title="VPN gateway degradation",
        incident_description=("Users are reporting authentication failures."),
        incident_severity="high",
        reasoning_summary=("The user explicitly requested incident creation."),
    )

    mock_live_status.return_value = ServiceStatus(
        service_name="vpn-gateway",
        status="degraded",
        message="Authentication latency is elevated.",
    )

    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000008"),
        username="support",
        roles=["it_support"],
    )

    incidents_before = db_session.scalars(select(IncidentModel)).all()

    incident_count_before = len(incidents_before)

    response = call_agent(
        current_user=support_user,
        question=("Create an incident for the degraded vpn-gateway."),
        session=db_session,
    )

    assert response.action == "create_incident"
    assert response.approval_required is True

    assert response.approval_id is not None
    assert response.approval_id.startswith("APR-")

    assert response.incident_id is None

    assert response.proposed_incident is not None

    assert response.proposed_incident.service_name == "vpn-gateway"

    assert response.proposed_incident.severity == "high"

    assert "Current service status: degraded" in response.proposed_incident.description

    assert "Authentication latency is elevated." in response.proposed_incident.description

    mock_live_status.assert_called_once_with(
        service_name="vpn-gateway",
    )

    db_session.expire_all()

    incidents_after = db_session.scalars(select(IncidentModel)).all()

    assert len(incidents_after) == incident_count_before

    pending = db_session.get(
        PendingIncidentActionModel,
        response.approval_id,
    )

    assert pending is not None
    assert pending.approved is False
    assert pending.executed is False


@patch("ai_it_support_assistant.services.agent_service.get_live_service_status")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_reader_cannot_propose_incident(
    mock_route_agent_request: Mock,
    mock_live_status: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="create_incident",
        service_name="vpn-gateway",
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        incident_title="VPN gateway degradation",
        incident_description=("Users are reporting authentication failures."),
        incident_severity="high",
        reasoning_summary=("The user requested incident creation."),
    )

    reader = User(
        user_id=UUID("00000000-0000-0000-0000-000000000009"),
        username="reader",
        roles=["reader"],
    )

    pending_before = db_session.scalars(select(PendingIncidentActionModel)).all()

    incidents_before = db_session.scalars(select(IncidentModel)).all()

    with pytest.raises(ToolAuthorizationError):
        call_agent(
            current_user=reader,
            question=("Create an incident for vpn-gateway."),
            session=db_session,
        )

    mock_live_status.assert_not_called()

    pending_after = db_session.scalars(select(PendingIncidentActionModel)).all()

    incidents_after = db_session.scalars(select(IncidentModel)).all()

    assert len(pending_after) == len(pending_before)

    assert len(incidents_after) == len(incidents_before)


@patch("ai_it_support_assistant.services.agent_service.get_live_service_status")
@patch("ai_it_support_assistant.services.agent_service.route_agent_request")
def test_incident_without_service_does_not_call_live_status(
    mock_route_agent_request: Mock,
    mock_live_status: Mock,
    db_session: Session,
) -> None:
    mock_route_agent_request.return_value = AgentDecision(
        action="create_incident",
        service_name=None,
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        incident_title="Employee login failures",
        incident_description=("Multiple employees report login failures."),
        incident_severity="medium",
        reasoning_summary=("The user explicitly requested a ticket."),
    )

    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000010"),
        username="support",
        roles=["it_support"],
    )

    response = call_agent(
        current_user=support_user,
        question=("Create a ticket for employee login failures."),
        session=db_session,
    )

    assert response.action == "create_incident"
    assert response.approval_required is True
    assert response.incident_id is None

    mock_live_status.assert_not_called()
