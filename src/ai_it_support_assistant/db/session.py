from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_it_support_assistant.core.config import (
    get_settings,
)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

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
def get_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
