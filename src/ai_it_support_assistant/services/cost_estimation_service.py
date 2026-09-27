from ai_it_support_assistant.observability.metrics import (
    LLM_ESTIMATED_COST_TOTAL,
    LLM_INPUT_TOKENS,
    LLM_OUTPUT_TOKENS,
)


def estimate_llm_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_rate: float,
    output_rate: float,
) -> float:
    """Estimate direct LLM cost for one request.

    Rates are expected to be expressed as cost per one million tokens.
    """

    if input_tokens < 0:
        raise ValueError("input_tokens cannot be negative")

    if output_tokens < 0:
        raise ValueError("output_tokens cannot be negative")

    if input_rate < 0:
        raise ValueError("input_rate cannot be negative")

    if output_rate < 0:
        raise ValueError("output_rate cannot be negative")

    input_cost = (input_tokens / 1_000_000) * input_rate

    output_cost = (output_tokens / 1_000_000) * output_rate

    return input_cost + output_cost


def estimate_cost_per_thousand_requests(
    *,
    average_request_cost: float,
) -> float:
    """Estimate cost for 1,000 requests."""

    if average_request_cost < 0:
        raise ValueError("average_request_cost cannot be negative")

    return average_request_cost * 1_000


def calculate_cache_hit_ratio(
    *,
    hits: int,
    misses: int,
) -> float:
    """Return cache hit ratio from 0.0 to 1.0."""

    if hits < 0:
        raise ValueError("hits cannot be negative")

    if misses < 0:
        raise ValueError("misses cannot be negative")

    total = hits + misses

    if total == 0:
        return 0.0

    return hits / total


def record_llm_usage(
    *,
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    input_rate: float,
    output_rate: float,
) -> float:
    """Record token usage and estimated cost in Prometheus.

    Returns the estimated request cost so callers may also
    log/store it in benchmark results.
    """

    estimated_cost = estimate_llm_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_rate=input_rate,
        output_rate=output_rate,
    )

    labels = {
        "model": model,
        "operation": operation,
    }

    LLM_INPUT_TOKENS.labels(**labels).inc(input_tokens)

    LLM_OUTPUT_TOKENS.labels(**labels).inc(output_tokens)

    LLM_ESTIMATED_COST_TOTAL.labels(**labels).inc(estimated_cost)

    return estimated_cost


def calculate_hit_ratio(
    *,
    hits: int,
    misses: int,
) -> float:
    total = hits + misses

    if total == 0:
        return 0.0

    return hits / total
