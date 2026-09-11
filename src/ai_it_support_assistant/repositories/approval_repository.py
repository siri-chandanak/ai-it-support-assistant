from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    PendingIncidentActionModel,
)
from ai_it_support_assistant.schemas.approval import (
    PendingIncidentAction,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)


class ConcurrentActionUpdateError(Exception):
    pass


def save_pending_action(
    *,
    session: Session,
    action: PendingIncidentAction,
) -> None:
    model = PendingIncidentActionModel(
        approval_id=action.approval_id,
        action=action.action,
        requested_by=action.requested_by,
        incident_title=action.incident.title,
        incident_description=action.incident.description,
        incident_severity=action.incident.severity,
        service_name=action.incident.service_name,
        state=action.state,
        version=action.version,
        incident_id=action.incident_id,
        failure_reason=action.failure_reason,
    )

    session.add(model)
    session.flush()


def get_pending_action(
    *,
    session: Session,
    approval_id: str,
) -> PendingIncidentAction | None:
    model = session.get(
        PendingIncidentActionModel,
        approval_id,
    )

    if model is None:
        return None

    return PendingIncidentAction(
        approval_id=model.approval_id,
        action=model.action,
        requested_by=model.requested_by,
        incident=IncidentCreateRequest(
            title=model.incident_title,
            description=model.incident_description,
            severity=model.incident_severity,
            service_name=model.service_name,
        ),
        state=model.state,
        version=model.version,
        incident_id=model.incident_id,
        failure_reason=model.failure_reason,
        execution_started_at=model.execution_started_at,
        completed_at=model.completed_at,
    )


def mark_pending_action_approved(
    *,
    session: Session,
    approval_id: str,
) -> bool:
    model = session.get(
        PendingIncidentActionModel,
        approval_id,
    )

    if model is None:
        return False

    model.approved = True
    model.approved_at = datetime.now(UTC)

    session.flush()

    return True


def mark_pending_action_executed(
    *,
    session: Session,
    approval_id: str,
    incident_id: str,
) -> bool:
    model = session.get(
        PendingIncidentActionModel,
        approval_id,
    )

    if model is None:
        return False

    model.executed = True
    model.incident_id = incident_id
    model.executed_at = datetime.now(UTC)

    session.flush()

    return True


def get_incident_id_for_pending_action(
    *,
    session: Session,
    approval_id: str,
) -> str | None:
    model = session.get(
        PendingIncidentActionModel,
        approval_id,
    )

    if model is None:
        return None

    return model.incident_id


def transition_action_state(
    *,
    session: Session,
    approval_id: str,
    expected_state: str,
    target_state: str,
    expected_version: int,
) -> int:
    statement = (
        update(PendingIncidentActionModel)
        .where(
            PendingIncidentActionModel.approval_id == approval_id,
            PendingIncidentActionModel.state == expected_state,
            PendingIncidentActionModel.version == expected_version,
        )
        .values(
            state=target_state,
            version=expected_version + 1,
        )
    )

    result = session.execute(statement)

    if result.rowcount != 1:
        raise ConcurrentActionUpdateError("Action state changed concurrently.")

    session.flush()

    return expected_version + 1


def claim_action_for_execution(
    *,
    session: Session,
    approval_id: str,
    expected_version: int,
) -> int:
    now = datetime.now(UTC)

    statement = (
        update(PendingIncidentActionModel)
        .where(
            PendingIncidentActionModel.approval_id == approval_id,
            PendingIncidentActionModel.state == "approved",
            PendingIncidentActionModel.version == expected_version,
        )
        .values(
            state="executing",
            execution_started_at=now,
            version=expected_version + 1,
        )
    )

    result = session.execute(statement)

    if result.rowcount != 1:
        raise ConcurrentActionUpdateError("Action could not be claimed for execution.")

    session.flush()

    return expected_version + 1


def mark_action_succeeded(
    *,
    session: Session,
    approval_id: str,
    expected_version: int,
    incident_id: str,
) -> int:
    now = datetime.now(UTC)

    statement = (
        update(PendingIncidentActionModel)
        .where(
            PendingIncidentActionModel.approval_id == approval_id,
            PendingIncidentActionModel.state == "executing",
            PendingIncidentActionModel.version == expected_version,
        )
        .values(
            state="succeeded",
            incident_id=incident_id,
            completed_at=now,
            failure_reason=None,
            version=expected_version + 1,
        )
    )

    result = session.execute(statement)

    if result.rowcount != 1:
        raise ConcurrentActionUpdateError("Action could not be marked succeeded.")

    session.flush()

    return expected_version + 1


def mark_action_failed(
    *,
    session: Session,
    approval_id: str,
    expected_version: int,
    failure_reason: str,
) -> int:
    now = datetime.now(UTC)

    statement = (
        update(PendingIncidentActionModel)
        .where(
            PendingIncidentActionModel.approval_id == approval_id,
            PendingIncidentActionModel.state == "executing",
            PendingIncidentActionModel.version == expected_version,
        )
        .values(
            state="failed",
            failure_reason=failure_reason,
            completed_at=now,
            version=expected_version + 1,
        )
    )

    result = session.execute(statement)

    if result.rowcount != 1:
        raise ConcurrentActionUpdateError("Action could not be marked failed.")

    session.flush()

    return expected_version + 1
