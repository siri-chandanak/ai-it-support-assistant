from sqlalchemy.orm import Session

from ai_it_support_assistant.evaluation.models import (
    PolicyEvaluationCase,
    PolicyEvaluationResult,
    PolicyEvaluationSummary,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyRequest,
)
from ai_it_support_assistant.services.pdp.base import (
    PolicyDecisionPoint,
)


def evaluate_policy_case(
    *,
    case: PolicyEvaluationCase,
    pdp: PolicyDecisionPoint,
    session: Session,
) -> PolicyEvaluationResult:
    decision = pdp.decide(
        request=PolicyRequest(
            subject=case.subject,
            action=case.action,
            resource=case.resource,
            context=case.context,
        ),
        session=session,
    )

    decision_correct = decision.allowed == case.expected_allowed

    reason_correct = (
        case.expected_reason_code is None or decision.reason_code == case.expected_reason_code
    )

    false_allow = case.expected_allowed is False and decision.allowed is True

    false_deny = case.expected_allowed is True and decision.allowed is False

    return PolicyEvaluationResult(
        case_id=case.case_id,
        description=case.description,
        expected_allowed=case.expected_allowed,
        actual_allowed=decision.allowed,
        expected_reason_code=(case.expected_reason_code),
        actual_reason_code=(decision.reason_code),
        policy_id=decision.policy_id,
        decision_correct=decision_correct,
        reason_correct=reason_correct,
        false_allow=false_allow,
        false_deny=false_deny,
        passed=(decision_correct and reason_correct),
    )


def build_policy_evaluation_summary(
    results: list[PolicyEvaluationResult],
) -> PolicyEvaluationSummary:
    total_cases = len(results)

    passed_cases = sum(result.passed for result in results)

    failed_cases = total_cases - passed_cases

    expected_allows = sum(result.expected_allowed for result in results)

    expected_denies = total_cases - expected_allows

    false_allows = sum(result.false_allow for result in results)

    false_denies = sum(result.false_deny for result in results)

    correct_allows = sum(result.expected_allowed and result.actual_allowed for result in results)

    correct_denies = sum(
        (not result.expected_allowed and not result.actual_allowed) for result in results
    )

    pass_rate = passed_cases / total_cases if total_cases else 0.0

    allow_accuracy = correct_allows / expected_allows if expected_allows else 1.0

    deny_accuracy = correct_denies / expected_denies if expected_denies else 1.0

    return PolicyEvaluationSummary(
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=pass_rate,
        expected_allows=expected_allows,
        expected_denies=expected_denies,
        false_allows=false_allows,
        false_denies=false_denies,
        allow_accuracy=allow_accuracy,
        deny_accuracy=deny_accuracy,
        results=results,
    )


def evaluate_policy_cases(
    *,
    cases: list[PolicyEvaluationCase],
    pdp: PolicyDecisionPoint,
    session: Session,
) -> PolicyEvaluationSummary:
    results = [
        evaluate_policy_case(
            case=case,
            pdp=pdp,
            session=session,
        )
        for case in cases
    ]

    return build_policy_evaluation_summary(results)


def policy_security_gate_passed(
    summary: PolicyEvaluationSummary,
) -> bool:
    return summary.false_allows == 0 and summary.failed_cases == 0
