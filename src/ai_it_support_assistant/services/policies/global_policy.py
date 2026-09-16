from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)

ACTION_PERMISSION_MAP: dict[str, str] = {
    "knowledge.read": "knowledge:read",
    "service_status.read": "service-status:read",
    "kubernetes.read": "kubernetes:read",
    "incident.create": "incident:create",
    "deployment.restart": "deployment:restart",
    "action.read": "action:read",
}


def evaluate_global_policy(
    request: PolicyRequest,
) -> PolicyDecision | None:
    if request.subject.disabled:
        return PolicyDecision(
            allowed=False,
            reason_code="subject_disabled",
            reason="Subject is disabled.",
            policy_id="global-subject-policy-v1",
        )

    required_permission = ACTION_PERMISSION_MAP.get(request.action)

    if required_permission is None:
        return PolicyDecision(
            allowed=False,
            reason_code="unknown_action",
            reason="Unknown policy action.",
            policy_id="global-permission-v1",
        )

    if required_permission not in request.subject.permissions:
        return PolicyDecision(
            allowed=False,
            reason_code="missing_permission",
            reason=("Required capability permission is missing."),
            policy_id="global-permission-v1",
        )

    return None
