from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from ai_it_support_assistant.models.incident import IncidentModel
from ai_it_support_assistant.schemas.incident import (
    IncidentExecutionResult,
    IncidentRecord,
)


def test_incident_idempotency_key_is_unique(db_session):
    suffix = uuid4().hex[:12].upper()

    shared_idempotency_key = f"create_incident:APR-{suffix}"

    first = IncidentModel(
        incident_id=f"INC-{uuid4().hex[:8].upper()}",
        title="VPN issue one",
        description="VPN issue",
        severity="medium",
        service_name="vpn",
        created_by="alice",
        status="open",
        idempotency_key=shared_idempotency_key,
    )

    second = IncidentModel(
        incident_id=f"INC-{uuid4().hex[:8].upper()}",
        title="VPN issue two",
        description="VPN issue",
        severity="medium",
        service_name="vpn",
        created_by="alice",
        status="open",
        idempotency_key=shared_idempotency_key,
    )

    db_session.add(first)
    db_session.commit()

    db_session.add(second)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_incident_execution_result_distinguishes_created_from_reused():
    incident = IncidentRecord(
        incident_id="INC-TEST-001",
        title="VPN outage",
        description="VPN authentication failing",
        severity="medium",
        service_name="vpn",
        created_by="alice",
        created_at=datetime.now(UTC),
    )

    created = IncidentExecutionResult(
        incident=incident,
        created=True,
    )

    reused = IncidentExecutionResult(
        incident=incident,
        created=False,
    )

    assert created.created is True
    assert reused.created is False
    assert created.incident.incident_id == "INC-TEST-001"
    assert reused.incident.incident_id == "INC-TEST-001"
