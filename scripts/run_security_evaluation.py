import json
from datetime import UTC, datetime
from pathlib import Path

from ai_it_support_assistant.core.config import (
    get_settings,
)
from ai_it_support_assistant.evaluation.security_evaluator import (
    build_authorization_summary,
    evaluate_authorization_case,
    load_authorization_cases,
)


def main() -> None:
    settings = get_settings()

    cases = load_authorization_cases(Path("data/evaluation/security_cases.json"))

    results = [
        evaluate_authorization_case(
            case=case,
            settings=settings,
        )
        for case in cases
    ]

    summary = build_authorization_summary(results)

    output = json.dumps(summary.model_dump(), indent=2)

    print(output)

    results_directory = Path("data/evaluation/results/")
    results_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    output_path = results_directory / f"security-evaluation-{timestamp}.json"

    output_path.write_text(
        output,
        encoding="utf-8",
    )

    print(f"\nSaved evaluation report to: {output_path}")


if __name__ == "__main__":
    main()
