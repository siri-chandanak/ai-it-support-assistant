from ai_it_support_assistant.schemas.tools import ServiceStatus

_service_statuses: dict[str, ServiceStatus] = {
    "ai-support-api": ServiceStatus(
        service_name="ai-support-api",
        status="healthy",
        message="All instances are responding.",
    ),
    "vpn-gateway": ServiceStatus(
        service_name="vpn-gateway",
        status="degraded",
        message="Authentication latency is elevated.",
    ),
    "identity-service": ServiceStatus(
        service_name="identity-service",
        status="healthy",
        message="Authentication service is operational.",
    ),
}


def get_service_status(
    service_name: str,
) -> ServiceStatus | None:
    return _service_statuses.get(service_name.lower())
