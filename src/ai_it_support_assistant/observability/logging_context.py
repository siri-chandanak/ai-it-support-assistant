from __future__ import annotations

import logging
from contextvars import Token

from ai_it_support_assistant.core.request_context import (
    get_request_id,
    request_id_context,
)
from ai_it_support_assistant.observability.tracing import (
    get_current_span_id,
    get_current_trace_id,
)


def set_request_id(request_id: str | None) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


class LoggingContextFilter(logging.Filter):
    """
    Inject request and OpenTelemetry correlation identifiers into
    every LogRecord handled by the configured logger/handler.

    Fields added:
        request_id
        trace_id
        span_id
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.trace_id = get_current_trace_id() or "-"
        record.span_id = get_current_span_id() or "-"

        return True


def add_logging_context_filter(
    logger: logging.Logger,
) -> None:
    """
    Add LoggingContextFilter to all handlers attached to a logger.

    Safe to call repeatedly.
    """
    for handler in logger.handlers:
        if any(
            isinstance(existing_filter, LoggingContextFilter) for existing_filter in handler.filters
        ):
            continue

        handler.addFilter(LoggingContextFilter())
