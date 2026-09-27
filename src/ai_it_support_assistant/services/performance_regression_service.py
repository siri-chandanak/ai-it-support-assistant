def regression_ratio(
    *,
    current: float,
    previous: float,
) -> float:
    if previous <= 0:
        return 1.0

    return current / previous


def exceeds_regression_limit(
    *,
    current: float,
    previous: float,
    maximum_ratio: float,
) -> bool:
    return (
        regression_ratio(
            current=current,
            previous=previous,
        )
        > maximum_ratio
    )
