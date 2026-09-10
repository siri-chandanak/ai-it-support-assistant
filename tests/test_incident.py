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

    incident = create_incident(
        session=db_session,
        request=request,
        created_by="support",
    )

    db_session.commit()

    assert incident.incident_id.startswith("INC-")
    assert incident.created_by == "support"
    assert incident.status == "open"
