from ai_it_support_assistant.services.performance_regression_service import (
    exceeds_regression_limit,
    regression_ratio,
)


def test_regression_ratio() -> None:
    assert (
        regression_ratio(
            current=125,
            previous=100,
        )
        == 1.25
    )


def test_regression_limit() -> None:
    assert exceeds_regression_limit(
        current=130,
        previous=100,
        maximum_ratio=1.25,
    )
