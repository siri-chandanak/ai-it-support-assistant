from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRestartActionPayload,
)


def parse_incident_payload(
    payload_json: str,
) -> IncidentCreateRequest:
    return IncidentCreateRequest.model_validate_json(payload_json)


def parse_restart_payload(
    payload_json: str,
) -> DeploymentRestartActionPayload:
    return DeploymentRestartActionPayload.model_validate_json(payload_json)
