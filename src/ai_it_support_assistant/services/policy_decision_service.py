import logging
import time

from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)
from ai_it_support_assistant.services.pdp.base import (
    PolicyDecisionPoint,
)

logger = logging.getLogger(__name__)


class PolicyDecisionUnavailableError(Exception):
    pass


def decide_policy(
    *,
    pdp: PolicyDecisionPoint,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    started_at = time.perf_counter()

    try:
        decision = pdp.decide(
            request=request,
            session=session,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - started_at) * 1000
        logger.exception(
            ("policy_decision_failed action=%s resource_type=%s duration_ms=%.3f"),
            request.action,
            request.resource.resource_type,
            duration_ms,
        )

        raise PolicyDecisionUnavailableError("Authorization service unavailable.") from exc

    duration_ms = (time.perf_counter() - started_at) * 1000

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
