import json
from datetime import UTC, datetime
from pathlib import Path

from ai_it_support_assistant.core.config import (
    get_settings,
)
from ai_it_support_assistant.db.session import (
    get_session_factory,
)
from ai_it_support_assistant.evaluation.models import (
    PolicyEvaluationCase,
)
from ai_it_support_assistant.evaluation.policy_evaluator import (
    evaluate_policy_cases,
    policy_security_gate_passed,
)
from ai_it_support_assistant.services.pdp.factory import (
    get_policy_decision_point,
)

DATASET_PATH = Path("data/evaluation/policy_cases.json")

RESULTS_DIRECTORY = Path("data/evaluation/results")


def load_cases() -> list[PolicyEvaluationCase]:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    return [PolicyEvaluationCase.model_validate(item) for item in payload]


def print_summary(summary) -> None:
    print()
    print("Policy Evaluation")
    print("-----------------")

    print(f"Cases:           {summary.total_cases}")
    print(f"Passed:          {summary.passed_cases}")
    print(f"Failed:          {summary.failed_cases}")

    print()

    print(f"False allows:    {summary.false_allows}")
    print(f"False denies:    {summary.false_denies}")

    print()

    print(f"Allow accuracy: {summary.allow_accuracy:.2%}")
    print(f"Deny accuracy:  {summary.deny_accuracy:.2%}")
    print(f"Pass rate:      {summary.pass_rate:.2%}")

    failed_results = [result for result in summary.results if not result.passed]

    if failed_results:
        print()
        print("Failed Cases")
        print("------------")

        for result in failed_results:
            print(f"{result.case_id}: {result.description}")

            print(f"  Expected: {result.expected_allowed} {result.expected_reason_code}")

            print(f"  Actual:   {result.actual_allowed} {result.actual_reason_code}")

    print()

    if policy_security_gate_passed(summary):
        print("SECURITY GATE: PASS")
    else:
        print("SECURITY GATE: FAIL")


def save_summary(summary) -> Path:
    RESULTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    result_path = RESULTS_DIRECTORY / (f"policy-evaluation-{timestamp}.json")

    result_path.write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return result_path


def main() -> None:
    settings = get_settings()

    pdp = get_policy_decision_point(
        mode=settings.policy_pdp_mode,
    )

    session_factory = get_session_factory(settings.database_url)

    cases = load_cases()

    with session_factory() as session:
        summary = evaluate_policy_cases(
            cases=cases,
            pdp=pdp,
            session=session,
        )

    print_summary(summary)

    result_path = save_summary(summary)

    print(f"Saved result: {result_path}")

    if not policy_security_gate_passed(summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
