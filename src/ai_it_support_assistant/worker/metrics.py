from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    PendingActionModel,
)
from ai_it_support_assistant.observability.metrics import (
    ACTION_EXECUTING,
    ACTION_QUEUE_DEPTH,
)


def refresh_action_queue_metrics(
    *,
    session: Session,
) -> None:
    """
    Refresh Prometheus worker gauges from PostgreSQL.

    PostgreSQL is the authoritative source of truth for action state,
    so these gauges are calculated directly from pending_actions rather
    than being maintained only with process-local increments/decrements.
    """

    # ---------------------------------------------------------
    # Approved actions waiting for a worker
    # ---------------------------------------------------------

    approved_count = session.scalar(
        select(func.count())
        .select_from(PendingActionModel)
        .where(PendingActionModel.state == "approved")
    )

    ACTION_QUEUE_DEPTH.set(int(approved_count or 0))

    # ---------------------------------------------------------
    # Actions currently executing, grouped by action type
    # ---------------------------------------------------------
    #
    # Clear previous labeled gauge values first.
    #
    # Example:
    #
    # Previous poll:
    # restart_deployment = 1
    #
    # Current poll:
    # restart_deployment = 0
    #
    # The GROUP BY query would no longer return restart_deployment,
    # so without clear(), Prometheus could continue exposing the
    # previous value of 1.
    # ---------------------------------------------------------

    ACTION_EXECUTING.clear()

    executing_rows = session.execute(
        select(
            PendingActionModel.action,
            func.count(),
        )
        .where(PendingActionModel.state == "executing")
        .group_by(PendingActionModel.action)
    ).all()

    for action_type, count in executing_rows:
        ACTION_EXECUTING.labels(
            action_type=action_type,
        ).set(count)
