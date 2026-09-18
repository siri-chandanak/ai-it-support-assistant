import httpx
import pytest

from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.pdp.local import (
    LocalPolicyDecisionPoint,
)
from ai_it_support_assistant.services.pdp.opa import (
    OPAPolicyDecisionPoint,
)


def make_service_status_request(
    *,
    permissions: list[str],
    disabled: bool = False,
) -> PolicyRequest:
    return PolicyRequest(
        subject=PolicySubject(
            subject_id="alice",
            username="alice",
            roles=["it_support"],
            permissions=permissions,
            disabled=disabled,
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="vpn-gateway",
            attributes={
                "service_name": "vpn-gateway",
            },
        ),
        context=PolicyContext(
            attributes={
                "policy_input_version": "1",
            },
        ),
    )


def opa_is_available() -> bool:
    try:
        response = httpx.get(
            "http://127.0.0.1:8181/health",
            timeout=1.0,
        )

        return response.status_code == 200

    except httpx.HTTPError:
        return False


@pytest.mark.integration
def test_local_and_opa_policy_parity(
    db_session,
) -> None:
    if not opa_is_available():
        pytest.skip("OPA is not running on localhost:8181")

    local_pdp = LocalPolicyDecisionPoint()

    opa_pdp = OPAPolicyDecisionPoint(
        opa_url="http://127.0.0.1:8181",
        policy_path="ai_it_support/authz/decision",
        timeout_seconds=2,
        max_attempts=1,
    )

    cases = [
        make_service_status_request(
            permissions=[
                "service-status:read",
            ],
        ),
        make_service_status_request(
            permissions=[],
        ),
        make_service_status_request(
            permissions=[
                "service-status:read",
            ],
            disabled=True,
        ),
    ]

    for request in cases:
        local_decision = local_pdp.decide(
            request=request,
            session=db_session,
        )

        opa_decision = opa_pdp.decide(
            request=request,
        )

        assert opa_decision.allowed == (local_decision.allowed)

        assert opa_decision.reason_code == (local_decision.reason_code)

        assert opa_decision.policy_id == (local_decision.policy_id)

        assert opa_decision.obligations == (local_decision.obligations)
