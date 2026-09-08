"""SQLAlchemy engine и сессии. SQLite из коробки, схема под PostgreSQL."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None
_SQLITE_BUSY_TIMEOUT_SEC = 30.0


def sqlite_url(path: str) -> str:
    resolved = Path(path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved}"


def ensure_schema(engine: Engine) -> None:
    """create_all does not add columns to existing tables."""
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(summaries)").fetchall()
        if not rows:
            return
        cols = {row[1] for row in rows}
        if "edited" not in cols:
            conn.exec_driver_sql(
                "ALTER TABLE summaries ADD COLUMN edited BOOLEAN NOT NULL DEFAULT 0"
            )


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            sqlite_url(settings.SQLITE_PATH),
            future=True,
            connect_args={
                "check_same_thread": False,
                "timeout": _SQLITE_BUSY_TIMEOUT_SEC,
            },
        )

        @event.listens_for(_engine, "connect")
        def _sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.fetchall()
            cursor.execute(f"PRAGMA busy_timeout={int(_SQLITE_BUSY_TIMEOUT_SEC * 1000)}")
            cursor.close()

        SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
    return _engine


def reset_engine() -> None:
    global _engine, SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    SessionLocal = None


def get_session() -> Generator[Session, None, None]:
    get_engine()
    assert SessionLocal is not None
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
