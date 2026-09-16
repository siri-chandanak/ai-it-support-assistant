from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)
from ai_it_support_assistant.services.audit_service import (
    record_audit_event,
)


def record_policy_decision(
    *,
    source_session: Session,
    request: PolicyRequest,
    decision: PolicyDecision,
) -> None:
    bind = source_session.get_bind()

    engine = (
        bind.engine
        if hasattr(bind, "engine")
        else bind
    )

    with Session(
        bind=engine,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as audit_session:
        record_audit_event(
            session=audit_session,
            event_type="POLICY_DECISION",
            actor=request.subject.username,
            action_type=request.action,
            resource_id=(
                request.resource.resource_id
            ),
            details={
                "subject_id": (
                    request.subject.subject_id
                ),
                "resource_type": (
                    request.resource.resource_type
                ),
                "allowed": str(
                    decision.allowed
                ).lower(),
                "reason_code": (
                    decision.reason_code
                ),
                "policy_id": (
                    decision.policy_id
                ),
                "obligations": ",".join(
                    decision.obligations
                ),
            },
        )

        audit_session.commit()