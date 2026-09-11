from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    PendingActionModel,
)
from ai_it_support_assistant.schemas.approval import (
    PendingAction,
)
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
)


class ConcurrentActionUpdateError(Exception):
    pass


def save_pending_action(
    *,
    session: Session,
    action: PendingAction,
) -> None:
    """
    Persist a validated pending action.

    payload_json is the canonical action-specific payload.

    Legacy incident columns are temporarily populated only for
    create_incident actions while the application transitions to
    the generic pending_actions model.
    """
    incident = None

    if action.action == "create_incident":
        incident = parse_incident_payload(action.payload_json)

    model = PendingActionModel(
        approval_id=action.approval_id,
        requested_by=action.requested_by,
        action=action.action,
        payload_json=action.payload_json,
        state=action.state,
        version=action.version,
        resource_id=action.resource_id,
        execution_token=action.execution_token,
        failure_reason=action.failure_reason,
        execution_started_at=(action.execution_started_at),
        completed_at=action.completed_at,
        incident_title=(incident.title if incident is not None else None),
        incident_description=(incident.description if incident is not None else None),
        incident_severity=(incident.severity if incident is not None else None),
        service_name=(incident.service_name if incident is not None else None),
        incident_id=(action.resource_id if action.action == "create_incident" else None),
    )

    session.add(model)
    session.flush()


def get_pending_action(
    *,
    session: Session,
    approval_id: str,
) -> PendingAction | None:
    model = session.get(
        PendingActionModel,
        approval_id,
    )

    if model is None:
        return None

    return PendingAction(
        approval_id=model.approval_id,
        action=model.action,
        requested_by=model.requested_by,
        payload_json=model.payload_json,
        state=model.state,
        resource_id=model.resource_id,
        execution_token=model.execution_token,
        failure_reason=model.failure_reason,
        version=model.version,
        execution_started_at=model.execution_started_at,
        completed_at=model.completed_at,
    )


def mark_pending_action_approved(
    *,
    session: Session,
    approval_id: str,
) -> bool:
    """
    Transition:
        pending -> approved

    This does NOT execute the external action.
    """
    model = session.get(
        PendingActionModel,
        approval_id,
    )

    if model is None:
        return False

    if model.state != "pending":
        return False

    model.state = "approved"
    model.approved_at = datetime.now(UTC)
    model.version += 1

    session.flush()

    return True


def mark_pending_action_executed(
    *,
    session: Session,
    approval_id: str,
    incident_id: str,
) -> bool:
    """
    Temporary backwards-compatible helper for
    create_incident.

    New generic action execution should prefer
    mark_action_succeeded().
    """
    model = session.get(
        PendingActionModel,
        approval_id,
    )

    if model is None:
        return False

    model.state = "succeeded"

    # Generic result field.
    model.resource_id = incident_id

    # Temporary backwards-compatible incident field.
    if model.action == "create_incident":
        model.incident_id = incident_id

    model.completed_at = datetime.now(UTC)
    model.failure_reason = None
    model.version += 1

    session.flush()

    return True


def get_incident_id_for_pending_action(
    *,
    session: Session,
    approval_id: str,
) -> str | None:
    """
    Temporary incident-specific compatibility helper.

    Eventually callers should use resource_id directly.
    """
    model = session.get(
        PendingActionModel,
        approval_id,
    )

    if model is None:
        return None

    if model.action != "create_incident":
        return None

    return model.resource_id


def transition_action_state(
    *,
    session: Session,
    approval_id: str,
    expected_state: str,
    target_state: str,
    expected_version: int,
) -> int:
    """
    Perform an optimistic-concurrency-protected state transition.

    Both the expected state and expected version must still match.
    """
    statement = (
        update(PendingActionModel)
        .where(
            PendingActionModel.approval_id == approval_id,
            PendingActionModel.state == expected_state,
            PendingActionModel.version == expected_version,
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
    """
    Atomically claim an approved action.

    Transition:
        approved -> executing

    Only the caller that successfully performs this update
    is allowed to execute the external write.
    """
    now = datetime.now(UTC)

    statement = (
        update(PendingActionModel)
        .where(
            PendingActionModel.approval_id == approval_id,
            PendingActionModel.state == "approved",
            PendingActionModel.version == expected_version,
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
    resource_id: str,
) -> int:
    """
    Transition:
        executing -> succeeded

    resource_id is generic:
      create_incident     -> INC-123
      restart_deployment  -> dev/payment-api
    """
    now = datetime.now(UTC)

    model = session.get(
        PendingActionModel,
        approval_id,
    )

    if model is None:
        raise ConcurrentActionUpdateError("Action does not exist.")

    values: dict[str, object] = {
        "state": "succeeded",
        "resource_id": resource_id,
        "completed_at": now,
        "failure_reason": None,
        "version": expected_version + 1,
    }

    # Temporary compatibility while create_incident still
    # uses the legacy incident_id database column.
    if model.action == "create_incident":
        values["incident_id"] = resource_id

    statement = (
        update(PendingActionModel)
        .where(
            PendingActionModel.approval_id == approval_id,
            PendingActionModel.state == "executing",
            PendingActionModel.version == expected_version,
        )
        .values(**values)
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
    """
    Transition:
        executing -> failed
    """
    now = datetime.now(UTC)

    statement = (
        update(PendingActionModel)
        .where(
            PendingActionModel.approval_id == approval_id,
            PendingActionModel.state == "executing",
            PendingActionModel.version == expected_version,
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


def set_action_execution_token(
    *,
    session: Session,
    approval_id: str,
    expected_version: int,
    execution_token: str,
    resource_id: str,
) -> int:
    """
    Persist the deterministic external-write token.

    For restart_deployment this is the exact restartedAt
    timestamp that will be sent to Kubernetes.

    The token is persisted BEFORE the external Kubernetes
    PATCH occurs.
    """

    statement = (
        update(PendingActionModel)
        .where(
            PendingActionModel.approval_id == approval_id,
            PendingActionModel.state == "executing",
            PendingActionModel.version == expected_version,
            PendingActionModel.execution_token.is_(None),
        )
        .values(
            execution_token=execution_token,
            resource_id=resource_id,
            version=expected_version + 1,
        )
    )

    result = session.execute(statement)

    if result.rowcount != 1:
        raise ConcurrentActionUpdateError("Execution token could not be persisted.")

    session.flush()

    return expected_version + 1
