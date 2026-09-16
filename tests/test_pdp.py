from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.pdp.factory import (
    get_policy_decision_point,
)
from ai_it_support_assistant.services.pdp.local import (
    LocalPolicyDecisionPoint,
)
from ai_it_support_assistant.services.policy_decision_service import (
    PolicyDecisionUnavailableError,
    decide_policy,
)


class BrokenPDP:
    def decide(
        self,
        *,
        request,
        session,
    ):
        raise RuntimeError("PDP unavailable")


def test_unsupported_pdp_mode_fails():
    get_policy_decision_point.cache_clear()

    with pytest.raises(
        ValueError,
        match="Unsupported PDP mode",
    ):
        get_policy_decision_point(
            mode="spaceship",
        )


def test_local_pdp_can_be_created():
    get_policy_decision_point.cache_clear()

    pdp = get_policy_decision_point(
        mode="local",
    )

    assert pdp is not None
    assert isinstance(
        pdp,
        LocalPolicyDecisionPoint,
    )


def test_pdp_failure_fails_closed():
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=PolicySubject(
            subject_id="alice",
            username="alice",
            permissions=[
                "deployment:restart",
            ],
        ),
        action="deployment.restart",
        resource=PolicyResource(
            resource_type="deployment",
            resource_id="team-a-dev/api",
        ),
    )

    with pytest.raises(PolicyDecisionUnavailableError):
        decide_policy(
            pdp=BrokenPDP(),
            request=request,
            session=session,
        )
