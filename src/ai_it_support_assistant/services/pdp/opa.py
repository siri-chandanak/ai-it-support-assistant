from __future__ import annotations

import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from ai_it_support_assistant.observability.metrics import (
    OPA_DURATION,
    OPA_FAILURES,
    OPA_REQUESTS,
    OPA_TIMEOUTS,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)


class ExternalPDPError(Exception):
    """Base exception for external PDP failures."""


class ExternalPDPTimeoutError(ExternalPDPError):
    """OPA did not respond before the configured timeout."""


class ExternalPDPUnavailableError(ExternalPDPError):
    """OPA could not be reached or returned a server-side failure."""


class ExternalPDPInvalidResponseError(ExternalPDPError):
    """OPA responded, but its response violated our policy contract."""


class OPAResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: PolicyDecision


def build_opa_input(
    request: PolicyRequest,
) -> dict[str, Any]:
    return {
        "input": request.model_dump(mode="json"),
    }


class OPAPolicyDecisionPoint:
    def __init__(
        self,
        *,
        opa_url: str,
        policy_path: str,
        timeout_seconds: float,
        max_attempts: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self._decision_url = f"{opa_url.rstrip('/')}/v1/data/{policy_path.strip('/')}"

        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts

        self._owns_client = client is None

        self._client = client or httpx.Client(
            timeout=timeout_seconds,
        )

    def decide(
        self,
        *,
        request: PolicyRequest,
        session=None,
    ) -> PolicyDecision:
        payload = build_opa_input(request)

        last_error: ExternalPDPError | None = None

        for attempt in range(
            1,
            self._max_attempts + 1,
        ):
            # One metric request represents one real HTTP attempt.
            # If OPA is retried, each retry is another request.
            OPA_REQUESTS.inc()

            request_started_at = time.perf_counter()

            try:
                response = self._client.post(
                    self._decision_url,
                    json=payload,
                )

                if response.status_code >= 500:
                    OPA_FAILURES.inc()

                    raise ExternalPDPUnavailableError("OPA returned a server error.")

                if response.status_code != 200:
                    OPA_FAILURES.inc()

                    raise ExternalPDPInvalidResponseError(
                        f"OPA returned an unexpected HTTP status: {response.status_code}"
                    )

                try:
                    body = response.json()

                    opa_response = OPAResponse.model_validate(body)

                except (
                    ValueError,
                    ValidationError,
                ) as exc:
                    OPA_FAILURES.inc()

                    raise ExternalPDPInvalidResponseError(
                        "OPA returned an invalid policy response."
                    ) from exc

                # Important:
                # allowed=False is NOT a failure.
                #
                # A valid policy DENY means OPA worked
                # correctly and returned a policy decision.
                return opa_response.result

            except httpx.TimeoutException as exc:
                OPA_TIMEOUTS.inc()
                OPA_FAILURES.inc()

                last_error = ExternalPDPTimeoutError("OPA policy evaluation timed out.")

                if attempt == self._max_attempts:
                    raise last_error from exc

            except httpx.HTTPError as exc:
                OPA_FAILURES.inc()

                last_error = ExternalPDPUnavailableError("OPA policy service is unavailable.")

                if attempt == self._max_attempts:
                    raise last_error from exc

            except ExternalPDPUnavailableError as exc:
                # OPA_FAILURES was already incremented
                # when the server-side failure was detected.
                last_error = exc

                if attempt == self._max_attempts:
                    raise

            except ExternalPDPInvalidResponseError:
                # Invalid responses are not transient.
                # Retrying normally would not help.
                #
                # OPA_FAILURES was already incremented
                # before this exception was raised.
                raise

            finally:
                OPA_DURATION.observe(time.perf_counter() - request_started_at)

            if attempt < self._max_attempts:
                delay_seconds = min(
                    0.1 * (2 ** (attempt - 1)),
                    1.0,
                )

                time.sleep(delay_seconds)

        if last_error is not None:
            raise last_error

        raise ExternalPDPUnavailableError("OPA evaluation failed unexpectedly.")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
