import logging
import time

from opentelemetry.trace import Status, StatusCode
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.observability.tracing import (
    get_tracer,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
    PolicyTraceStep,
)
from ai_it_support_assistant.services.policies.global_policy import (
    evaluate_global_policy,
)
from ai_it_support_assistant.services.policies.incident_policy import (
    evaluate_incident_create_policy,
)
from ai_it_support_assistant.services.policies.kubernetes_policy import (
    evaluate_deployment_restart_policy,
    evaluate_kubernetes_read_policy,
)
from ai_it_support_assistant.services.policy_audit_service import (
    record_policy_decision,
)

logger = logging.getLogger(__name__)

tracer = get_tracer()


class PolicyEvaluationError(Exception):
    pass


def evaluate_policy(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    started_at = time.perf_counter()

    with tracer.start_as_current_span(
        "policy.evaluate",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        # Safe, bounded policy metadata.
        span.set_attribute(
            "policy.action",
            request.action,
        )

        span.set_attribute(
            "policy.resource_type",
            request.resource.resource_type,
        )

        try:
            decision = _evaluate_policy(
                request=request,
                session=session,
            )

            record_policy_decision(
                source_session=session,
                request=request,
                decision=decision,
            )

            duration_ms = (time.perf_counter() - started_at) * 1000

            span.set_attribute(
                "policy.allowed",
                decision.allowed,
            )

            span.set_attribute(
                "policy.reason_code",
                decision.reason_code,
            )

            span.set_attribute(
                "policy.policy_id",
                decision.policy_id,
            )

            span.set_attribute(
                "policy.duration_ms",
                duration_ms,
            )

            # IMPORTANT:
            # allowed=False is a valid policy result.
            #
            # Example:
            #   approval_required
            #   namespace_access_denied
            #   missing_permission
            #
            # These are NOT infrastructure failures,
            # so the span remains successful.
            logger.info(
                (
                    "policy_decision_completed "
                    "request_id=%s "
                    "decision_id=%s "
                    "username=%s "
                    "action=%s "
                    "resource_type=%s "
                    "resource_id=%s "
                    "allowed=%s "
                    "reason_code=%s "
                    "policy_id=%s "
                    "duration_ms=%.3f"
                ),
                get_request_id(),
                decision.decision_id,
                request.subject.username,
                request.action,
                request.resource.resource_type,
                request.resource.resource_id,
                decision.allowed,
                decision.reason_code,
                decision.policy_id,
                duration_ms,
            )

            return decision

        except SQLAlchemyError as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000

            span.record_exception(exc)

            span.set_attribute(
                "policy.failure_type",
                "database_error",
            )

            span.set_attribute(
                "policy.duration_ms",
                duration_ms,
            )

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Policy database operation failed.",
                )
            )

            logger.exception(
                (
                    "policy_evaluation_failed "
                    "request_id=%s "
                    "action=%s "
                    "resource_type=%s "
                    "failure_type=%s "
                    "duration_ms=%.3f"
                ),
                get_request_id(),
                request.action,
                request.resource.resource_type,
                "database_error",
                duration_ms,
            )

            raise PolicyEvaluationError("Policy data could not be loaded.") from exc

        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000

            span.record_exception(exc)

            span.set_attribute(
                "policy.failure_type",
                "evaluation_error",
            )

            span.set_attribute(
                "policy.duration_ms",
                duration_ms,
            )

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Policy evaluation failed.",
                )
            )

            logger.exception(
                (
                    "policy_evaluation_failed "
                    "request_id=%s "
                    "action=%s "
                    "resource_type=%s "
                    "failure_type=%s "
                    "duration_ms=%.3f"
                ),
                get_request_id(),
                request.action,
                request.resource.resource_type,
                "evaluation_error",
                duration_ms,
            )

            raise


def _evaluate_policy(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    trace: list[PolicyTraceStep] = []

    global_decision = evaluate_global_policy(
        request=request,
        trace=trace,
    )

    if global_decision is not None:
        return global_decision

    if request.action == "knowledge.read":
        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason="Knowledge access allowed.",
            policy_id="knowledge-read-v1",
        )

    if request.action == "service_status.read":
        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason="Service status access allowed.",
            policy_id="service-status-read-v1",
        )

    if request.action == "kubernetes.read":
        return evaluate_kubernetes_read_policy(
            request=request,
            session=session,
            trace=trace,
        )

    if request.action == "deployment.restart":
        return evaluate_deployment_restart_policy(
            request=request,
            session=session,
            trace=trace,
        )

    if request.action == "incident.create":
        return evaluate_incident_create_policy(
            request=request,
        )

    if request.action == "action.read":
        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason="Action read allowed.",
            policy_id="action-read-v1",
        )

    return PolicyDecision(
        allowed=False,
        reason_code="no_matching_allow_policy",
        reason="No policy explicitly allowed this action.",
        policy_id="default-deny-v1",
    )
