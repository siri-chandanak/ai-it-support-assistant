from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from ai_it_support_assistant.evaluation.models import (
    PolicyEvaluationCase,
)
from ai_it_support_assistant.evaluation.policy_evaluator import (
    evaluate_policy_case,
    evaluate_policy_cases,
    policy_security_gate_passed,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyDecision,
    PolicyResource,
    PolicySubject,
    PolicyTraceStep,
)


class AllowPDP:
    def decide(
        self,
        *,
        request,
        session,
    ):
        return PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason="Allowed.",
            policy_id="test-policy-v1",
        )


class DenyPDP:
    def decide(
        self,
        *,
        request,
        session,
    ):
        return PolicyDecision(
            allowed=False,
            reason_code="missing_permission",
            reason="Denied.",
            policy_id="test-policy-v1",
        )


def make_case(
    *,
    expected_allowed: bool,
    expected_reason_code: str,
) -> PolicyEvaluationCase:
    return PolicyEvaluationCase(
        case_id="test-001",
        description="Test case",
        subject=PolicySubject(
            subject_id="alice",
            username="alice",
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="vpn",
        ),
        context=PolicyContext(),
        expected_allowed=expected_allowed,
        expected_reason_code=(expected_reason_code),
    )


def test_policy_case_passes():
    session = MagicMock(spec=Session)
    case = make_case(
        expected_allowed=True,
        expected_reason_code="allowed",
    )

    result = evaluate_policy_case(
        case=case,
        pdp=AllowPDP(),
        session=session,
    )

    assert result.passed is True
    assert result.false_allow is False
    assert result.false_deny is False


def test_false_allow_is_detected():
    session = MagicMock(spec=Session)
    case = make_case(
        expected_allowed=False,
        expected_reason_code=("missing_permission"),
    )

    result = evaluate_policy_case(
        case=case,
        pdp=AllowPDP(),
        session=session,
    )

    assert result.false_allow is True
    assert result.passed is False


def test_false_deny_is_detected():
    session = MagicMock(spec=Session)
    case = make_case(
        expected_allowed=True,
        expected_reason_code="allowed",
    )

    result = evaluate_policy_case(
        case=case,
        pdp=DenyPDP(),
        session=session,
    )

    assert result.false_deny is True
    assert result.passed is False


def test_security_gate_fails_on_false_allow():
    session = MagicMock(spec=Session)
    case = make_case(
        expected_allowed=False,
        expected_reason_code=("missing_permission"),
    )

    summary = evaluate_policy_cases(
        cases=[case],
        pdp=AllowPDP(),
        session=session,
    )

    assert summary.false_allows == 1
    assert policy_security_gate_passed(summary) is False


def test_policy_decision_has_decision_id():
    decision = PolicyDecision(
        allowed=False,
        reason_code="missing_permission",
        reason="Denied.",
        policy_id="test-v1",
    )

    assert decision.decision_id.startswith("POL-")


def test_policy_decision_supports_trace():
    decision = PolicyDecision(
        allowed=False,
        reason_code="missing_permission",
        reason="Denied.",
        policy_id="test-v1",
        trace=[
            PolicyTraceStep(
                rule_id="permission_check",
                outcome="fail",
            )
        ],
    )

    assert len(decision.trace) == 1
    assert decision.trace[0].rule_id == "permission_check"
    assert decision.trace[0].outcome == "fail"
