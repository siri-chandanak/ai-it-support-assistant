import pytest

from ai_it_support_assistant.services.cost_estimation_service import (
    calculate_cache_hit_ratio,
    calculate_hit_ratio,
    estimate_cost_per_thousand_requests,
    estimate_llm_cost,
)


def test_estimate_llm_cost() -> None:
    cost = estimate_llm_cost(
        input_tokens=2_000,
        output_tokens=500,
        input_rate=1.0,
        output_rate=2.0,
    )

    assert cost == pytest.approx(0.003)


def test_estimate_cost_per_thousand_requests() -> None:
    cost = estimate_cost_per_thousand_requests(
        average_request_cost=0.003,
    )

    assert cost == pytest.approx(3.0)


def test_cache_hit_ratio() -> None:
    ratio = calculate_cache_hit_ratio(
        hits=80,
        misses=20,
    )

    assert ratio == pytest.approx(0.8)


def test_cache_hit_ratio_with_no_requests() -> None:
    ratio = calculate_cache_hit_ratio(
        hits=0,
        misses=0,
    )

    assert ratio == 0.0


def test_negative_token_count_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="input_tokens cannot be negative",
    ):
        estimate_llm_cost(
            input_tokens=-1,
            output_tokens=10,
            input_rate=1.0,
            output_rate=2.0,
        )


def test_calculate_hit_ratio() -> None:
    result = calculate_hit_ratio(
        hits=80,
        misses=20,
    )

    assert result == 0.8


def test_hit_ratio_is_zero_when_empty() -> None:
    result = calculate_hit_ratio(
        hits=0,
        misses=0,
    )

    assert result == 0.0
