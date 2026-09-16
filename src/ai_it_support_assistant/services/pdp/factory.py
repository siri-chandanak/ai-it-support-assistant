from functools import lru_cache

from ai_it_support_assistant.services.pdp.local import (
    LocalPolicyDecisionPoint,
)
from ai_it_support_assistant.services.pdp.opa import (
    OPAPolicyDecisionPoint,
)


@lru_cache(maxsize=8)
def get_policy_decision_point(
    *,
    mode: str,
    opa_url: str | None = None,
    opa_policy_path: str | None = None,
    opa_timeout_seconds: float | None = None,
    opa_max_attempts: int | None = None,
):
    normalized_mode = mode.strip().lower()

    if normalized_mode == "local":
        return LocalPolicyDecisionPoint()

    if normalized_mode == "opa":
        if opa_url is None:
            raise ValueError("opa_url is required when PDP mode is 'opa'")

        if opa_policy_path is None:
            raise ValueError("opa_policy_path is required when PDP mode is 'opa'")

        if opa_timeout_seconds is None:
            raise ValueError("opa_timeout_seconds is required when PDP mode is 'opa'")

        if opa_max_attempts is None:
            raise ValueError("opa_max_attempts is required when PDP mode is 'opa'")

        return OPAPolicyDecisionPoint(
            opa_url=opa_url,
            policy_path=opa_policy_path,
            timeout_seconds=opa_timeout_seconds,
            max_attempts=opa_max_attempts,
        )

    raise ValueError(f"Unsupported PDP mode: {mode!r}")


def create_policy_decision_point(
    *,
    mode: str,
    opa_url: str,
    opa_policy_path: str,
    opa_timeout_seconds: float,
    opa_max_attempts: int,
):
    normalized_mode = mode.strip().lower()

    if normalized_mode == "local":
        return LocalPolicyDecisionPoint()

    if normalized_mode == "opa":
        return OPAPolicyDecisionPoint(
            opa_url=opa_url,
            policy_path=opa_policy_path,
            timeout_seconds=opa_timeout_seconds,
            max_attempts=opa_max_attempts,
        )

    raise ValueError(f"Unsupported policy PDP mode: {mode}")
