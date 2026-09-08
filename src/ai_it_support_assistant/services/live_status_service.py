from ai_it_support_assistant.repositories.service_status_repository import (
    get_service_status,
)
from ai_it_support_assistant.schemas.tools import ServiceStatus


class LiveToolError(Exception):
    pass


class ServiceNotFoundError(LiveToolError):
    pass


def get_live_service_status(
    *,
    service_name: str,
) -> ServiceStatus:
    normalized_name = service_name.strip().lower()

    if not normalized_name:
        raise LiveToolError("Service name is required.")

    status = get_service_status(normalized_name)

    if status is None:
        raise ServiceNotFoundError("Service was not found.")

    return status
