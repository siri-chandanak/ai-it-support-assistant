from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ai_it_support_assistant.db.session import get_session_factory


class DatabaseHealthError(Exception):
    """Raised when the database health check fails."""


def check_database_health(*, database_url: str) -> None:
    session_factory = get_session_factory(database_url)

    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise DatabaseHealthError("Database health check failed.") from exc
