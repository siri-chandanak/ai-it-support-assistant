from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.engine import Engine

from ai_it_support_assistant.core.config import get_settings

_instrumented_engine_ids: set[int] = set()


def instrument_database_engine(engine: Engine) -> None:
    settings = get_settings()

    if not settings.otel_enabled:
        return

    engine_id = id(engine)

    if engine_id in _instrumented_engine_ids:
        return

    SQLAlchemyInstrumentor().instrument(
        engine=engine,
    )

    _instrumented_engine_ids.add(engine_id)
