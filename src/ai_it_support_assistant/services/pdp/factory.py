from functools import lru_cache

from ai_it_support_assistant.services.pdp.base import (
    PolicyDecisionPoint,
)
from ai_it_support_assistant.services.pdp.local import (
    LocalPolicyDecisionPoint,
)


@lru_cache
def get_policy_decision_point(
    *,
    mode: str,
) -> PolicyDecisionPoint:
    normalized_mode = mode.strip().lower()

    if normalized_mode == "local":
        return LocalPolicyDecisionPoint()

    raise ValueError(f"Unsupported PDP mode: {mode!r}")
