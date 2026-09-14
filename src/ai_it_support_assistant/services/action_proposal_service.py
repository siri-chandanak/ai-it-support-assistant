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
from ai_it_support_assistant.services.kubernetes_state_service import (
    get_deployment_state,
)
from ai_it_support_assistant.services.kubernetes_write_policy_service import (
    KubernetesWritePolicyError,
    validate_restart_policy,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    authorize_tool,
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
    authorize_tool(
        tool_name="create_incident",
        user=current_user,
    )

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
    authorize_tool(
        tool_name="restart_deployment",
        user=current_user,
    )

    validate_restart_policy(
        namespace=namespace,
        deployment_name=deployment_name,
        write_enabled=kubernetes_write_enabled,
        allowed_namespaces_raw=(kubernetes_restart_allowed_namespaces),
        allowed_deployments_raw=(kubernetes_restart_allowed_deployments),
    )

    deployment_state = get_deployment_state(
        name=deployment_name,
        namespace=namespace,
        config_mode=kubernetes_config_mode,
        context=kubernetes_context,
    )

    if deployment_state.desired_replicas == 0:
        raise KubernetesWritePolicyError(
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
