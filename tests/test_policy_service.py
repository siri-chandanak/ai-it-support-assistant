import logging
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.audit import (
    AuditEventModel,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.policy_service import (
    PolicyEvaluationError,
    evaluate_policy,
)


def build_subject(
    *,
    permissions: list[str],
    disabled: bool = False,
) -> PolicySubject:
    return PolicySubject(
        subject_id="alice",
        username="alice",
        roles=["it_support"],
        permissions=permissions,
        disabled=disabled,
    )


def build_restart_request(
    *,
    phase: str = "proposal",
    writes_enabled: bool = True,
    approval_state: str | None = None,
    namespace: str = "team-a-dev",
    deployment_name: str = "payment-api",
) -> PolicyRequest:
    return PolicyRequest(
        subject=build_subject(
            permissions=[
                "deployment:restart",
            ],
        ),
        action="deployment.restart",
        resource=PolicyResource(
            resource_type="deployment",
            resource_id=(f"{namespace}/{deployment_name}"),
            attributes={
                "namespace": namespace,
                "deployment_name": (deployment_name),
            },
        ),
        context=PolicyContext(
            attributes={
                "phase": phase,
                "writes_enabled": (writes_enabled),
                "approval_state": (approval_state),
                "allowed_namespaces": [
                    "team-a-dev",
                ],
                "allowed_deployments": [
                    "payment-api",
                ],
            },
        ),
    )


def test_disabled_user_is_denied() -> None:
    request = PolicyRequest(
        subject=build_subject(
            permissions=["knowledge:read"],
            disabled=True,
        ),
        action="knowledge.read",
        resource=PolicyResource(
            resource_type="knowledge",
        ),
    )
    session = MagicMock(spec=Session)

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is False
    assert decision.reason_code == "subject_disabled"


def test_unknown_action_is_denied() -> None:
    request = PolicyRequest(
        subject=build_subject(
            permissions=[],
        ),
        action="shell.execute",
        resource=PolicyResource(
            resource_type="shell",
        ),
    )
    session = MagicMock(spec=Session)

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is False
    assert decision.reason_code == "unknown_action"


def test_missing_permission_is_denied() -> None:
    request = PolicyRequest(
        subject=build_subject(
            permissions=[],
        ),
        action="knowledge.read",
        resource=PolicyResource(
            resource_type="knowledge",
        ),
    )
    session = MagicMock(spec=Session)
    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is False
    assert decision.reason_code == "missing_permission"


def test_knowledge_read_is_allowed() -> None:
    request = PolicyRequest(
        subject=build_subject(
            permissions=["knowledge:read"],
        ),
        action="knowledge.read",
        resource=PolicyResource(
            resource_type="knowledge",
        ),
    )
    session = MagicMock(spec=Session)
    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.policy_id == "knowledge-read-v1"


def test_service_status_is_allowed() -> None:
    request = PolicyRequest(
        subject=build_subject(
            permissions=["service-status:read"],
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="payment-api",
        ),
    )
    session = MagicMock(spec=Session)
    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True


def test_kubernetes_read_allowed_for_namespace() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["kubernetes:read"],
        ),
        action="kubernetes.read",
        resource=PolicyResource(
            resource_type="kubernetes",
            resource_id=("team-a-dev/payment-api"),
            attributes={
                "namespace": "team-a-dev",
                "resource_kind": "deployment",
                "resource_name": "payment-api",
            },
        ),
    )

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=True,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.policy_id == "kubernetes-read-v1"


def test_kubernetes_read_denied_for_other_namespace() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["kubernetes:read"],
        ),
        action="kubernetes.read",
        resource=PolicyResource(
            resource_type="kubernetes",
            resource_id=("team-b-dev/payment-api"),
            attributes={
                "namespace": "team-b-dev",
                "resource_kind": "deployment",
                "resource_name": "payment-api",
            },
        ),
    )

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=False,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is False
    assert decision.reason_code == "namespace_access_denied"


def test_restart_proposal_allowed() -> None:
    session = MagicMock(spec=Session)

    request = build_restart_request()

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=True,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"

    assert "explicit_approval" in decision.obligations


def test_restart_denied_when_writes_disabled() -> None:
    session = MagicMock(spec=Session)

    request = build_restart_request(
        writes_enabled=False,
    )

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=True,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is False
    assert decision.reason_code == "kubernetes_writes_disabled"


def test_restart_denied_for_global_namespace() -> None:
    session = MagicMock(spec=Session)

    request = build_restart_request(
        namespace="production",
    )

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=True,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is False
    assert decision.reason_code == "namespace_not_globally_allowed"


def test_restart_denied_without_namespace_grant() -> None:
    session = MagicMock(spec=Session)

    request = build_restart_request()

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=False,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is False
    assert decision.reason_code == "namespace_access_denied"


def test_restart_execution_requires_approval() -> None:
    session = MagicMock(spec=Session)

    request = build_restart_request(
        phase="execution",
        approval_state="pending",
    )

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=True,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is False
    assert decision.reason_code == "approval_required"


def test_restart_execution_allowed_when_approved() -> None:
    session = MagicMock(spec=Session)

    request = build_restart_request(
        phase="execution",
        approval_state="approved",
    )

    with patch(
        "ai_it_support_assistant.services.policies.kubernetes_policy.has_resource_permission",
        return_value=True,
    ):
        decision = evaluate_policy(
            request=request,
            session=session,
        )

    assert decision.allowed is True


def test_incident_proposal_allowed() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["incident:create"],
        ),
        action="incident.create",
        resource=PolicyResource(
            resource_type="incident",
        ),
        context=PolicyContext(
            attributes={
                "phase": "proposal",
            },
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"
    assert decision.policy_id == "incident-create-v1"


def test_incident_execution_requires_approval() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["incident:create"],
        ),
        action="incident.create",
        resource=PolicyResource(
            resource_type="incident",
        ),
        context=PolicyContext(
            attributes={
                "phase": "execution",
                "approval_state": "pending",
            },
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is False
    assert decision.reason_code == "approval_required"


def test_incident_execution_allowed_when_approved() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["incident:create"],
        ),
        action="incident.create",
        resource=PolicyResource(
            resource_type="incident",
        ),
        context=PolicyContext(
            attributes={
                "phase": "execution",
                "approval_state": "approved",
            },
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True


def test_policy_allow_is_audited(
    db_session,
):
    request = PolicyRequest(
        subject=PolicySubject(
            subject_id="user-1",
            username="support",
            roles=["it_support"],
            permissions=["service-status:read"],
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="payment-api",
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=db_session,
    )

    assert decision.allowed is True

    event = db_session.scalar(
        select(AuditEventModel)
        .where(
            AuditEventModel.event_type
            == "POLICY_DECISION"
        )
        .order_by(
            AuditEventModel.created_at.desc()
        )
    )

    assert event is not None
    assert event.actor == "support"
    assert event.action_type == (
        "service_status.read"
    )
    assert event.resource_id == "payment-api"

def test_policy_deny_is_audited(
    db_session,
):
    request = PolicyRequest(
        subject=PolicySubject(
            subject_id="user-2",
            username="reader",
            roles=["reader"],
            permissions=[],
        ),
        action="deployment.restart",
        resource=PolicyResource(
            resource_type="kubernetes",
            resource_id="dev/payment-api",
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=db_session,
    )

    assert decision.allowed is False

    event = db_session.scalar(
        select(AuditEventModel)
        .where(
            AuditEventModel.event_type
            == "POLICY_DECISION"
        )
        .order_by(
            AuditEventModel.created_at.desc()
        )
    )

    assert event is not None
    assert event.actor == "reader"
    assert event.action_type == (
        "deployment.restart"
    )

def test_policy_evaluation_failure_is_logged(
    monkeypatch,
    db_session,
    caplog,
):
    request = PolicyRequest(
        subject=PolicySubject(
            subject_id="user-1",
            username="support",
            roles=["it_support"],
            permissions=[
                "kubernetes:read",
            ],
        ),
        action="kubernetes.read",
        resource=PolicyResource(
            resource_type="kubernetes",
            resource_id="dev/payment-api",
            attributes={
                "namespace": "dev",
                "resource_kind": "deployment",
                "resource_name": "payment-api",
            },
        ),
    )

    def fail_policy(*args, **kwargs):
        raise OperationalError(
            statement=None,
            params=None,
            orig=Exception(
                "database unavailable"
            ),
        )

    monkeypatch.setattr(
        (
            "ai_it_support_assistant.services."
            "policy_service._evaluate_policy"
        ),
        fail_policy,
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            PolicyEvaluationError
        ):
            evaluate_policy(
                request=request,
                session=db_session,
            )

    assert "policy_evaluation_failed" in caplog.text
    assert "username=support" in caplog.text
    assert "action=kubernetes.read" in caplog.text
    assert "resource_type=kubernetes" in caplog.text