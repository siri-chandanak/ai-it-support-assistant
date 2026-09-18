import logging
import time

from opentelemetry.trace import Status, StatusCode
from sqlalchemy.orm import Session

from ai_it_support_assistant.observability.tracing import get_tracer
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)
from ai_it_support_assistant.services.pdp.base import (
    PolicyDecisionPoint,
)

logger = logging.getLogger(__name__)

tracer = get_tracer()


class PolicyDecisionUnavailableError(Exception):
    pass


def decide_policy(
    *,
    pdp: PolicyDecisionPoint,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    started_at = time.perf_counter()

    with tracer.start_as_current_span("policy.evaluate") as span:
        span.set_attribute(
            "policy.action",
            request.action,
        )
        span.set_attribute(
            "policy.resource_type",
            request.resource.resource_type,
        )

        try:
            decision = pdp.decide(
                request=request,
                session=session,
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000

            span.record_exception(exc)

            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "authorization service unavailable",
                )
            )

            logger.exception(
                ("policy_decision_failed action=%s resource_type=%s duration_ms=%.3f"),
                request.action,
                request.resource.resource_type,
                duration_ms,
            )

            raise PolicyDecisionUnavailableError("Authorization service unavailable.") from exc

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

        logger.info(
            "policy_decision_completed",
            extra={
                "decision_id": decision.decision_id,
                "policy_id": decision.policy_id,
                "allowed": decision.allowed,
                "reason_code": decision.reason_code,
                "duration_ms": round(
                    duration_ms,
                    3,
                ),
            },
        )

        return decision
