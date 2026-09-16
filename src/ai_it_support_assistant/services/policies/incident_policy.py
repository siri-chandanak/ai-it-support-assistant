from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)


def evaluate_incident_create_policy(
    *,
    request: PolicyRequest,
) -> PolicyDecision:
    phase = request.context.attributes.get("phase")

    approval_state = request.context.attributes.get("approval_state")

    if phase not in {
        "proposal",
        "execution",
        "reconciliation",
    }:
        return PolicyDecision(
            allowed=False,
            reason_code="invalid_phase",
            reason=("Unknown incident policy phase."),
            policy_id="incident-create-v1",
        )

    if phase == "execution":
        if approval_state != "approved":
            return PolicyDecision(
                allowed=False,
                reason_code="approval_required",
                reason=("Approved action state is required for execution."),
                policy_id="incident-create-v1",
            )

    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Incident creation allowed.",
        policy_id="incident-create-v1",
        obligations=[
            "explicit_approval",
            "audit_execution",
        ],
    )
