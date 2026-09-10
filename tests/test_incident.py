from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.incident_service import (
    create_incident,
)


def test_create_incident_returns_id(
    db_session,
) -> None:
    request = IncidentCreateRequest(
        title="VPN gateway degradation",
        description=("Authentication latency is elevated."),
        severity="high",
        service_name="vpn-gateway",
    )

    result = create_incident(
        session=db_session,
        request=request,
        created_by="support",
        idempotency_key=("create_incident:APR-TEST-001"),
    )

    assert result.incident.incident_id.startswith("INC-")

    assert result.created is True
