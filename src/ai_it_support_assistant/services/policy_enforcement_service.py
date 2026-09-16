from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
)


class AuthorizationDeniedError(Exception):
    def __init__(
        self,
        decision: PolicyDecision,
    ) -> None:
        super().__init__(decision.reason)
        self.decision = decision


def enforce_policy(
    decision: PolicyDecision,
) -> None:
    if not decision.allowed:
        raise AuthorizationDeniedError(decision)
