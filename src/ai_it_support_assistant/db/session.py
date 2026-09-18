from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_it_support_assistant.core.config import (
    get_settings,
)
from ai_it_support_assistant.observability.database import (
    instrument_database_engine,
)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


instrument_database_engine(engine)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@lru_cache
def get_session_factory(
    database_url: str,
) -> sessionmaker:
    database_engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    instrument_database_engine(database_engine)

    return sessionmaker(
        bind=database_engine,
        autoflush=False,
        expire_on_commit=False,
    )
