from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
    PolicyRequest,
)
from ai_it_support_assistant.services.policy_service import (
    evaluate_policy,
)


class LocalPolicyDecisionPoint:
    def decide(
        self,
        *,
        request: PolicyRequest,
        session: Session,
    ) -> PolicyDecision:
        return evaluate_policy(
            request=request,
            session=session,
        )
