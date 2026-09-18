import time

from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import (
    get_settings,
)
from ai_it_support_assistant.observability.metrics import (
    POLICY_DECISIONS,
    POLICY_DENIALS,
    POLICY_DURATION,
    POLICY_ERRORS,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyDecision,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.pdp.factory import (
    get_policy_decision_point,
)
from ai_it_support_assistant.services.permission_service import (
    get_user_permissions,
)
from ai_it_support_assistant.services.policy_decision_service import (
    decide_policy,
)


def _authorize(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    settings = get_settings()

    request.context.attributes.setdefault(
        "policy_input_version",
        settings.policy_input_version,
    )

    pdp = get_policy_decision_point(
        mode=settings.policy_pdp_mode,
        opa_url=settings.opa_url,
        opa_policy_path=settings.opa_policy_path,
        opa_timeout_seconds=settings.opa_timeout_seconds,
        opa_max_attempts=settings.opa_max_attempts,
    )

    start = time.perf_counter()

    try:
        decision = decide_policy(
            pdp=pdp,
            request=request,
            session=session,
        )

    except Exception:
        POLICY_ERRORS.labels(
            action=request.action,
            pdp_mode=settings.policy_pdp_mode,
        ).inc()

        raise

    finally:
        POLICY_DURATION.labels(
            action=request.action,
            pdp_mode=settings.policy_pdp_mode,
        ).observe(time.perf_counter() - start)

    result = "allow" if decision.allowed else "deny"

    POLICY_DECISIONS.labels(
        action=request.action,
        result=result,
        reason_code=decision.reason_code,
        pdp_mode=settings.policy_pdp_mode,
    ).inc()

    if not decision.allowed:
        POLICY_DENIALS.labels(
            action=request.action,
            reason_code=decision.reason_code,
            pdp_mode=settings.policy_pdp_mode,
        ).inc()

    return decision


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

    namespace_globally_allowed = namespace in allowed_namespaces

    deployment_globally_allowed = deployment_name in allowed_deployments

    request = PolicyRequest(
        subject=subject,
        action="deployment.restart",
        resource=PolicyResource(
            resource_type="deployment",
            resource_id=f"{namespace}/{deployment_name}",
            attributes={
                "namespace": namespace,
                "resource_kind": "deployment",
                "resource_name": deployment_name,
            },
        ),
        context=PolicyContext(
            attributes={
                "phase": phase,
                "writes_enabled": writes_enabled,
                "namespace_globally_allowed": (namespace_globally_allowed),
                "deployment_globally_allowed": (deployment_globally_allowed),
                "approval_state": approval_state,
            },
        ),
    )

    return _authorize(
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

    return _authorize(
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

    return _authorize(
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

    return _authorize(
        request=request,
        session=session,
    )
