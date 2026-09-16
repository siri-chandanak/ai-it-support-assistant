import httpx

from ai_it_support_assistant.services.pdp.opa import (
    ExternalPDPTimeoutError,
    ExternalPDPUnavailableError,
)


def check_opa_health(
    *,
    opa_url: str,
    timeout_seconds: float,
    require_bundle_ready: bool = False,
) -> None:
    health_path = "/health?bundles" if require_bundle_ready else "/health"
    health_url = f"{opa_url.rstrip('/')}{health_path}"

    try:
        response = httpx.get(
            health_url,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ExternalPDPTimeoutError("OPA health check timed out.") from exc
    except httpx.HTTPError as exc:
        raise ExternalPDPUnavailableError("OPA health check failed.") from exc

    if response.status_code != 200:
        raise ExternalPDPUnavailableError(f"OPA health check returned HTTP {response.status_code}.")
