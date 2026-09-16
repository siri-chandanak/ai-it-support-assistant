from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyDecision,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.permission_service import (
    get_user_permissions,
)
from ai_it_support_assistant.services.policy_service import (
    evaluate_policy,
)


def build_policy_subject(
    user,
) -> PolicySubject:
    permissions = sorted(get_user_permissions(user.roles))

    return PolicySubject(
        subject_id=str(user.user_id),
        username=user.username,
        roles=list(user.roles),
        permissions=permissions,
        disabled=user.disabled,
    )


def authorize_deployment_restart(
    *,
    subject,
    namespace: str,
    deployment_name: str,
    phase: str,
    writes_enabled: bool,
    allowed_namespaces: list[str],
    allowed_deployments: list[str],
    session: Session,
    approval_state: str | None = None,
) -> PolicyDecision:
    request = PolicyRequest(
        subject=subject,
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
                "allowed_namespaces": (allowed_namespaces),
                "allowed_deployments": (allowed_deployments),
                "approval_state": (approval_state),
            },
        ),
    )

    return evaluate_policy(
        request=request,
        session=session,
    )


def authorize_incident_create(
    *,
    subject,
    phase: str,
    session: Session,
    approval_state: str | None = None,
) -> PolicyDecision:
    request = PolicyRequest(
        subject=subject,
        action="incident.create",
        resource=PolicyResource(
            resource_type="incident",
        ),
        context=PolicyContext(
            attributes={
                "phase": phase,
                "approval_state": (approval_state),
            },
        ),
    )

    return evaluate_policy(
        request=request,
        session=session,
    )


def authorize_service_status_read(
    *,
    subject,
    service_name: str,
    session: Session,
) -> PolicyDecision:
    request = PolicyRequest(
        subject=subject,
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id=service_name,
            attributes={
                "service_name": service_name,
            },
        ),
    )

    return evaluate_policy(
        request=request,
        session=session,
    )


def authorize_kubernetes_read(
    *,
    subject: PolicySubject,
    namespace: str,
    resource_type: str,
    resource_name: str,
    session: Session,
) -> PolicyDecision:
    request = PolicyRequest(
        subject=subject,
        action="kubernetes.read",
        resource=PolicyResource(
            resource_type="kubernetes",
            resource_id=(f"{namespace}/{resource_name}"),
            attributes={
                "namespace": namespace,
                "resource_kind": resource_type,
                "resource_name": resource_name,
            },
        ),
    )

    return evaluate_policy(
        request=request,
        session=session,
    )
