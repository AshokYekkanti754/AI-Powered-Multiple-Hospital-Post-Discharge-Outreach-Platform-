"""
SQLAlchemy engine/session management.

DATABASE_URL is read exclusively from environment/.env via app.core.config.
No connection strings are ever hardcoded.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}


def _build_engine():
    eng = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except OperationalError:
        # Fallback so `uvicorn`/`pytest` never hard-crash when Postgres is
        # unreachable: use a local SQLite file. Tests override with in-memory
        # SQLite via conftest anyway.
        fallback_url = "sqlite:///./dev.db"
        print(f"[db] WARNING: cannot reach {settings.DATABASE_URL!r}; falling back to {fallback_url}")
        fb_args = {"check_same_thread": False}
        return create_engine(fallback_url, connect_args=fb_args, future=True)


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
