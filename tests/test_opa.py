import httpx
import pytest

from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.pdp.opa import (
    ExternalPDPInvalidResponseError,
    ExternalPDPUnavailableError,
    OPAPolicyDecisionPoint,
)


def make_policy_request() -> PolicyRequest:
    return PolicyRequest(
        subject=PolicySubject(
            subject_id="alice",
            username="alice",
            roles=["it_support"],
            permissions=["service-status:read"],
            disabled=False,
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
            attributes={},
        ),
    )


def make_opa_client(
    handler,
) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
    )


def test_opa_returns_allow() -> None:
    policy_request = make_policy_request()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "allowed": True,
                    "reason_code": "allowed",
                    "reason": "Allowed.",
                    "policy_id": "test-policy-v1",
                    "obligations": [],
                    "trace": [],
                }
            },
        )

    client = make_opa_client(handler)

    pdp = OPAPolicyDecisionPoint(
        opa_url="http://opa:8181",
        policy_path="ai_it_support/authz/decision",
        timeout_seconds=2,
        max_attempts=1,
        client=client,
    )

    decision = pdp.decide(
        request=policy_request,
    )

    assert decision.allowed is True
    assert decision.reason_code == "allowed"


def test_opa_valid_deny_is_not_error() -> None:
    policy_request = make_policy_request()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "result": {
                    "allowed": False,
                    "reason_code": "missing_permission",
                    "reason": "Permission missing.",
                    "policy_id": "test-policy-v1",
                    "obligations": [],
                    "trace": [],
                }
            },
        )

    client = make_opa_client(handler)

    pdp = OPAPolicyDecisionPoint(
        opa_url="http://opa:8181",
        policy_path="ai_it_support/authz/decision",
        timeout_seconds=2,
        max_attempts=1,
        client=client,
    )

    decision = pdp.decide(
        request=policy_request,
    )

    assert decision.allowed is False
    assert decision.reason_code == "missing_permission"


def test_opa_missing_result_fails_closed() -> None:
    policy_request = make_policy_request()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={},
        )

    client = make_opa_client(handler)

    pdp = OPAPolicyDecisionPoint(
        opa_url="http://opa:8181",
        policy_path="ai_it_support/authz/decision",
        timeout_seconds=2,
        max_attempts=1,
        client=client,
    )

    with pytest.raises(ExternalPDPInvalidResponseError):
        pdp.decide(
            request=policy_request,
        )


def test_opa_500_is_unavailable() -> None:
    policy_request = make_policy_request()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            500,
        )

    client = make_opa_client(handler)

    pdp = OPAPolicyDecisionPoint(
        opa_url="http://opa:8181",
        policy_path="ai_it_support/authz/decision",
        timeout_seconds=2,
        max_attempts=1,
        client=client,
    )

    with pytest.raises(ExternalPDPUnavailableError):
        pdp.decide(
            request=policy_request,
        )
