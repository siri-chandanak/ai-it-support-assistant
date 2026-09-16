from typing import Protocol

from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)


class PolicyDecisionPoint(Protocol):
    def decide(
        self,
        *,
        request: PolicyRequest,
        session: Session,
    ) -> PolicyDecision:
        pass
