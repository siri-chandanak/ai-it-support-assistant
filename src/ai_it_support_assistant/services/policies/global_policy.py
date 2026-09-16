from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
    PolicyTraceStep,
)
from ai_it_support_assistant.services.policy_trace_service import (
    policy_trace_step,
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
    *,
    request: PolicyRequest,
    trace: list[PolicyTraceStep],
) -> PolicyDecision | None:
    subject_enabled = not request.subject.disabled

    trace.append(
        policy_trace_step(
            rule_id="subject_enabled",
            passed=subject_enabled,
        )
    )

    if not subject_enabled:
        return PolicyDecision(
            allowed=False,
            reason_code="subject_disabled",
            reason="Subject is disabled.",
            policy_id=("global-subject-policy-v1"),
            trace=trace,
        )

    required_permission = ACTION_PERMISSION_MAP.get(request.action)

    known_action = required_permission is not None

    trace.append(
        policy_trace_step(
            rule_id="known_action",
            passed=known_action,
        )
    )

    if required_permission is None:
        return PolicyDecision(
            allowed=False,
            reason_code="unknown_action",
            reason="Unknown policy action.",
            policy_id=("global-permission-v1"),
            trace=trace,
        )

    has_required_permission = required_permission in request.subject.permissions

    trace.append(
        policy_trace_step(
            rule_id=(f"permission_{request.action}"),
            passed=(has_required_permission),
        )
    )

    if not has_required_permission:
        return PolicyDecision(
            allowed=False,
            reason_code=("missing_permission"),
            reason=("Required capability permission is missing."),
            policy_id=("global-permission-v1"),
            trace=trace,
        )

    return None
