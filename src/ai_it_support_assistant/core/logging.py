import logging

from ai_it_support_assistant.observability.logging_context import (
    add_logging_context_filter,
)


def configure_logging(
    *,
    log_level: str,
) -> None:
    logging.basicConfig(
        level=getattr(
            logging,
            log_level.upper(),
            logging.INFO,
        ),
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "request_id=%(request_id)s "
            "trace_id=%(trace_id)s "
            "span_id=%(span_id)s "
            "%(message)s"
        ),
    )

    root_logger = logging.getLogger()

    add_logging_context_filter(
        root_logger,
    )
