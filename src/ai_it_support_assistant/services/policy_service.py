import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_it_support_assistant.core.request_context import (
    get_request_id,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
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


class PolicyEvaluationError(Exception):
    pass


def evaluate_policy(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
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

        return decision

    except SQLAlchemyError as exc:
        logger.error(
            (
                "policy_evaluation_failed "
                "request_id=%s "
                "username=%s "
                "action=%s "
                "resource_type=%s "
                "resource_id=%s"
            ),
            get_request_id(),
            request.subject.username,
            request.action,
            request.resource.resource_type,
            request.resource.resource_id,
        )

        raise PolicyEvaluationError("Policy data could not be loaded.") from exc


def _evaluate_policy(
    *,
    request: PolicyRequest,
    session: Session,
) -> PolicyDecision:
    global_decision = evaluate_global_policy(request)

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
            reason=("Service status access allowed."),
            policy_id=("service-status-read-v1"),
        )

    if request.action == "kubernetes.read":
        return evaluate_kubernetes_read_policy(
            request=request,
            session=session,
        )

    if request.action == "deployment.restart":
        return evaluate_deployment_restart_policy(
            request=request,
            session=session,
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
        reason_code=("no_matching_allow_policy"),
        reason=("No policy explicitly allowed this action."),
        policy_id="default-deny-v1",
    )
