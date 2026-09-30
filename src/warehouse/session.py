# src/warehouse/session.py
"""SQLAlchemy engine and session factory for the warehouse."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.logger import get_logger

log = get_logger(__name__)


def get_database_url() -> str:
    """Build the database URL from environment variables."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "rcol")
    password = os.getenv("POSTGRES_PASSWORD", "rcol_dev_password")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "regional_cost_of_living")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def create_engine_with_pool(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine with production-grade pooling."""
    url = database_url or get_database_url()
    engine = create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,      # validate connections before use
        pool_recycle=1800,       # recycle connections every 30 min
        echo=False,
        future=True,
    )
    log.info("engine_created", url=url.split("@")[-1])  # log host/db, not password
    return engine


_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def get_engine() -> Engine:
    """Return a singleton engine."""
    global _engine
    if _engine is None:
        _engine = create_engine_with_pool()
    return _engine


def get_session_factory() -> sessionmaker:
    """Return a singleton session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionFactory


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional session scope with automatic rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def health_check() -> bool:
    """Verify the database is reachable and responding to queries."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.error("db_health_check_failed", error=str(exc))
        return False
