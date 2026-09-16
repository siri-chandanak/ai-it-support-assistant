from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)
from ai_it_support_assistant.services.resource_permission_service import (
    has_resource_permission,
)


def evaluate_kubernetes_read_policy(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    namespace = request.resource.attributes.get("namespace")

    if not isinstance(namespace, str):
        return PolicyDecision(
            allowed=False,
            reason_code=("invalid_namespace"),
            reason=("A valid namespace is required."),
            policy_id="kubernetes-read-v1",
        )

    if not has_resource_permission(
        session=session,
        username=request.subject.username,
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value=namespace,
    ):
        return PolicyDecision(
            allowed=False,
            reason_code=("namespace_access_denied"),
            reason=("Subject cannot read this namespace."),
            policy_id="kubernetes-read-v1",
        )

    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Kubernetes read allowed.",
        policy_id="kubernetes-read-v1",
    )


def evaluate_deployment_restart_policy(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    namespace = request.resource.attributes.get("namespace")

    deployment_name = request.resource.attributes.get("deployment_name")

    phase = request.context.attributes.get("phase")

    writes_enabled = request.context.attributes.get("writes_enabled")

    approval_state = request.context.attributes.get("approval_state")

    allowed_namespaces = request.context.attributes.get(
        "allowed_namespaces",
        [],
    )

    allowed_deployments = request.context.attributes.get(
        "allowed_deployments",
        [],
    )

    if not isinstance(namespace, str):
        return PolicyDecision(
            allowed=False,
            reason_code="invalid_namespace",
            reason="A valid namespace is required.",
            policy_id="deployment-restart-v1",
        )

    if not isinstance(
        deployment_name,
        str,
    ):
        return PolicyDecision(
            allowed=False,
            reason_code=("invalid_deployment"),
            reason=("A valid deployment name is required."),
            policy_id="deployment-restart-v1",
        )

    if writes_enabled is not True:
        return PolicyDecision(
            allowed=False,
            reason_code=("kubernetes_writes_disabled"),
            reason=("Kubernetes write actions are disabled."),
            policy_id="deployment-restart-v1",
        )

    if namespace not in allowed_namespaces:
        return PolicyDecision(
            allowed=False,
            reason_code=("namespace_not_globally_allowed"),
            reason=("Namespace is outside restart policy."),
            policy_id="deployment-restart-v1",
        )

    if deployment_name not in allowed_deployments:
        return PolicyDecision(
            allowed=False,
            reason_code=("deployment_not_globally_allowed"),
            reason=("Deployment is outside restart policy."),
            policy_id="deployment-restart-v1",
        )

    if not has_resource_permission(
        session=session,
        username=request.subject.username,
        permission="deployment:restart",
        resource_type="namespace",
        resource_value=namespace,
    ):
        return PolicyDecision(
            allowed=False,
            reason_code=("namespace_access_denied"),
            reason=("Subject is not authorized for this namespace."),
            policy_id="deployment-restart-v1",
        )

    if phase == "execution":
        if approval_state != "approved":
            return PolicyDecision(
                allowed=False,
                reason_code=("approval_required"),
                reason=("Approved action state is required for execution."),
                policy_id="deployment-restart-v1",
            )

    if phase not in {
        "proposal",
        "execution",
        "reconciliation",
    }:
        return PolicyDecision(
            allowed=False,
            reason_code="invalid_phase",
            reason=("Unknown restart policy phase."),
            policy_id="deployment-restart-v1",
        )

    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason=("Deployment restart policy allowed."),
        policy_id="deployment-restart-v1",
        obligations=[
            "explicit_approval",
            "audit_execution",
            "verify_rollout",
        ],
    )
