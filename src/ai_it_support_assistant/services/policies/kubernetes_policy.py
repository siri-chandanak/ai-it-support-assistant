from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
    PolicyTraceStep,
)
from ai_it_support_assistant.services.policy_trace_service import (
    policy_trace_step,
)
from ai_it_support_assistant.services.resource_permission_service import (
    has_resource_permission,
)


def evaluate_kubernetes_read_policy(
    *,
    request: PolicyRequest,
    session: Session,
    trace: list[PolicyTraceStep],
) -> PolicyDecision:

    namespace = request.resource.attributes.get("namespace")

    namespace_valid = isinstance(namespace, str) and bool(namespace.strip())

    trace.append(
        policy_trace_step(
            rule_id="namespace_present",
            passed=namespace_valid,
        )
    )

    if not namespace_valid:
        return PolicyDecision(
            allowed=False,
            reason_code="invalid_namespace",
            reason=("Namespace is missing or invalid."),
            policy_id="kubernetes-read-v1",
            trace=trace,
        )

    namespace_allowed = has_resource_permission(
        session=session,
        username=(request.subject.username),
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value=namespace,
    )

    trace.append(
        policy_trace_step(
            rule_id="user_namespace_grant",
            passed=namespace_allowed,
        )
    )

    if not namespace_allowed:
        return PolicyDecision(
            allowed=False,
            reason_code=("namespace_access_denied"),
            reason=("Subject does not have access to this namespace."),
            policy_id="kubernetes-read-v1",
            trace=trace,
        )

    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason=("Kubernetes read is authorized."),
        policy_id="kubernetes-read-v1",
        trace=trace,
    )


def evaluate_deployment_restart_policy(
    *,
    request: PolicyRequest,
    session: Session,
    trace: list[PolicyTraceStep],
) -> PolicyDecision:
    namespace = request.resource.attributes.get("namespace")

    deployment_name = request.resource.attributes.get("resource_name")

    namespace_valid = isinstance(namespace, str) and bool(namespace.strip())

    trace.append(
        policy_trace_step(
            rule_id="namespace_present",
            passed=namespace_valid,
        )
    )

    if not namespace_valid:
        return PolicyDecision(
            allowed=False,
            reason_code="invalid_namespace",
            reason=("Namespace is missing or invalid."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    deployment_valid = isinstance(deployment_name, str) and bool(deployment_name.strip())

    trace.append(
        policy_trace_step(
            rule_id="deployment_present",
            passed=deployment_valid,
        )
    )

    if not deployment_valid:
        return PolicyDecision(
            allowed=False,
            reason_code="invalid_deployment",
            reason=("Deployment name is missing or invalid."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    writes_enabled = request.context.attributes.get("writes_enabled") is True

    trace.append(
        policy_trace_step(
            rule_id="writes_enabled",
            passed=writes_enabled,
        )
    )

    if not writes_enabled:
        return PolicyDecision(
            allowed=False,
            reason_code=("kubernetes_writes_disabled"),
            reason=("Kubernetes writes are disabled."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    namespace_globally_allowed = (
        request.context.attributes.get("namespace_globally_allowed") is True
    )

    trace.append(
        policy_trace_step(
            rule_id=("global_namespace_allowlist"),
            passed=(namespace_globally_allowed),
        )
    )

    if not namespace_globally_allowed:
        return PolicyDecision(
            allowed=False,
            reason_code=("namespace_not_globally_allowed"),
            reason=("Namespace is not globally allowed for restart."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    deployment_globally_allowed = (
        request.context.attributes.get("deployment_globally_allowed") is True
    )

    trace.append(
        policy_trace_step(
            rule_id=("global_deployment_allowlist"),
            passed=(deployment_globally_allowed),
        )
    )

    if not deployment_globally_allowed:
        return PolicyDecision(
            allowed=False,
            reason_code=("deployment_not_globally_allowed"),
            reason=("Deployment is not globally allowed for restart."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    namespace_granted = has_resource_permission(
        session=session,
        username=(request.subject.username),
        permission=("deployment:restart"),
        resource_type="namespace",
        resource_value=namespace,
    )

    trace.append(
        policy_trace_step(
            rule_id="user_namespace_grant",
            passed=namespace_granted,
        )
    )

    if not namespace_granted:
        return PolicyDecision(
            allowed=False,
            reason_code=("namespace_access_denied"),
            reason=("Subject is not authorized for this namespace."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    phase = request.context.attributes.get("phase")

    if phase == "execution":
        approval_state = request.context.attributes.get("approval_state")

        approved = approval_state == "approved"

        trace.append(
            policy_trace_step(
                rule_id="execution_approved",
                passed=approved,
            )
        )

        if not approved:
            return PolicyDecision(
                allowed=False,
                reason_code="approval_required",
                reason=("Execution requires an approved action."),
                policy_id="deployment-restart-v1",
                trace=trace,
            )

        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason=("Deployment restart execution is authorized."),
            policy_id="deployment-restart-v1",
            trace=trace,
        )

    if phase == "proposal":
        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason=("Deployment restart proposal is authorized."),
            policy_id="deployment-restart-v1",
            obligations=[
                "explicit_approval",
            ],
            trace=trace,
        )

    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Deployment restart is authorized.",
        policy_id="deployment-restart-v1",
        trace=trace,
    )
