from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.approval_repository import (
    PendingAction,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRestartActionPayload,
)
from ai_it_support_assistant.services.approval_service import (
    create_pending_action,
    create_pending_incident_action,
)
from ai_it_support_assistant.services.kubernetes_restart_validation_service import (
    KubernetesRestartValidationError,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    get_deployment_state,
)
from ai_it_support_assistant.services.policy_authorization_service import (
    authorize_deployment_restart,
    authorize_incident_create,
    build_policy_subject,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    enforce_policy,
)


def prepare_incident_action(
    *,
    session: Session,
    current_user: User,
    request: IncidentCreateRequest,
) -> PendingAction:
    """Validate and persist an incident proposal.

    This function creates a pending action only.
    It does not create the incident itself.
    """

    subject = build_policy_subject(current_user)

    policy_decision = authorize_incident_create(
        subject=subject,
        phase="proposal",
        session=session,
    )

    enforce_policy(policy_decision)

    pending = create_pending_incident_action(
        session=session,
        requested_by=current_user.username,
        incident=request,
    )

    return pending


def prepare_restart_action(
    *,
    session: Session,
    current_user: User,
    deployment_name: str,
    namespace: str,
    kubernetes_write_enabled: bool,
    kubernetes_restart_allowed_namespaces: str,
    kubernetes_restart_allowed_deployments: str,
    kubernetes_config_mode: str,
    kubernetes_context: str,
) -> tuple[PendingAction, DeploymentRestartActionPayload]:
    """Validate and persist a restart proposal.

    This function creates a pending action only.
    It does not restart the Deployment.
    """
    subject = build_policy_subject(
        current_user
    )

    policy_decision = authorize_deployment_restart(
        subject=subject,
        namespace=namespace,
        deployment_name=deployment_name,
        phase="proposal",
        writes_enabled=kubernetes_write_enabled,
        allowed_namespaces=[
            value.strip()
            for value in (
                kubernetes_restart_allowed_namespaces
                or ""
            ).split(",")
            if value.strip()
        ],
        allowed_deployments=[
            value.strip()
            for value in (
                kubernetes_restart_allowed_deployments
                or ""
            ).split(",")
            if value.strip()
        ],
        session=session,
    )

    enforce_policy(
        policy_decision
    )

    deployment_state = get_deployment_state(
        name=deployment_name,
        namespace=namespace,
        config_mode=kubernetes_config_mode,
        context=kubernetes_context,
    )

    if deployment_state.desired_replicas == 0:
        raise KubernetesRestartValidationError(
            "Cannot propose restart for a Deployment with zero desired replicas."
        )

    warnings: list[str] = []

    if deployment_state.desired_replicas == 1:
        warnings.append(
            "Deployment has one desired replica; restart may cause temporary unavailability."
        )

    restart_payload = DeploymentRestartActionPayload(
        name=deployment_state.name,
        namespace=deployment_state.namespace,
        evidence_desired_replicas=(deployment_state.desired_replicas),
        evidence_ready_replicas=(deployment_state.ready_replicas),
        evidence_available_replicas=(deployment_state.available_replicas),
        warnings=warnings,
    )

    pending = create_pending_action(
        session=session,
        requested_by=current_user.username,
        action_type="restart_deployment",
        payload_json=restart_payload.model_dump_json(),
    )

    return pending, restart_payload
