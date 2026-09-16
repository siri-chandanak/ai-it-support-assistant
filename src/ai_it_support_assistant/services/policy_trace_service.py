from ai_it_support_assistant.schemas.policy import (
    PolicyTraceStep,
)


def policy_trace_step(
    *,
    rule_id: str,
    passed: bool,
    detail: str | None = None,
) -> PolicyTraceStep:
    return PolicyTraceStep(
        rule_id=rule_id,
        outcome="pass" if passed else "fail",
        detail=detail,
    )
