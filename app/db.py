"""SQLAlchemy engine и сессии. SQLite из коробки, схема под PostgreSQL."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None
_SQLITE_BUSY_TIMEOUT_SEC = 30.0


def sqlite_url(path: str) -> str:
    resolved = Path(path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved}"


def resolve_database_url(url: str, *, data_dir: str = "./data") -> str:
    parsed = make_url(url)
    if parsed.drivername != "sqlite":
        return url

    database = unquote(parsed.database or "")
    if not database or database == ":memory:":
        return url

    db_path = Path(database).expanduser()
    if db_path.is_absolute():
        resolved = db_path
    else:
        # Anchor relative paths to DATA_DIR, not process cwd (Docker WORKDIR is /app).
        resolved = (Path(data_dir).expanduser().resolve() / db_path.name).resolve()

    resolved.parent.mkdir(parents=True, exist_ok=True)
    return parsed.set(database=str(resolved)).render_as_string(hide_password=False)


def database_url(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.DATABASE_URL:
        return resolve_database_url(settings.DATABASE_URL, data_dir=settings.DATA_DIR)
    return sqlite_url(settings.SQLITE_PATH)


def is_sqlite_url(url: str) -> bool:
    return make_url(url).drivername == "sqlite"


def is_sqlite_engine(engine: Engine) -> bool:
    return engine.dialect.name == "sqlite"


def _table_columns(conn, table: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _try_drop_column(conn, table: str, column: str) -> None:
    try:
        conn.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN {column}")
    except Exception:
        pass


def ensure_schema(engine: Engine) -> None:
    """SQLite-only patches for upgrades without Alembic; create_all skips new columns."""
    if not is_sqlite_engine(engine):
        return

    with engine.begin() as conn:
        summary_cols = _table_columns(conn, "summaries")
        if summary_cols and "edited" not in summary_cols:
            conn.exec_driver_sql(
                "ALTER TABLE summaries ADD COLUMN edited BOOLEAN NOT NULL DEFAULT 0"
            )

        tariff_cols = _table_columns(conn, "tariffs")
        if tariff_cols:
            if "price_per_1k_summary_chars" not in tariff_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE tariffs ADD COLUMN price_per_1k_summary_chars "
                    "NUMERIC(12, 6) NOT NULL DEFAULT 0"
                )
                if "price_per_generated_text" in tariff_cols:
                    conn.exec_driver_sql(
                        "UPDATE tariffs SET price_per_1k_summary_chars = price_per_generated_text"
                    )
            if "audio_retention_days" not in tariff_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE tariffs ADD COLUMN audio_retention_days INTEGER NOT NULL DEFAULT 0"
                )
            if "api_enabled" not in tariff_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE tariffs ADD COLUMN api_enabled BOOLEAN NOT NULL DEFAULT 1"
                )
            if "signup_credit" not in tariff_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE tariffs ADD COLUMN signup_credit NUMERIC(12, 2) NOT NULL DEFAULT 0"
                )
            if "price_per_generated_text" in _table_columns(conn, "tariffs"):
                _try_drop_column(conn, "tariffs", "price_per_generated_text")

        task_cols = _table_columns(conn, "tasks")
        if task_cols:
            if "snap_price_per_1k_summary_chars" not in task_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE tasks ADD COLUMN snap_price_per_1k_summary_chars "
                    "NUMERIC(12, 6) NOT NULL DEFAULT 0"
                )
                if "snap_price_per_generated_text" in task_cols:
                    conn.exec_driver_sql(
                        "UPDATE tasks SET snap_price_per_1k_summary_chars = snap_price_per_generated_text"
                    )
            if "snap_price_per_generated_text" in _table_columns(conn, "tasks"):
                _try_drop_column(conn, "tasks", "snap_price_per_generated_text")

        usage_cols = _table_columns(conn, "usage_events")
        if usage_cols and "summary_chars" not in usage_cols:
            conn.exec_driver_sql("ALTER TABLE usage_events ADD COLUMN summary_chars INTEGER")


def get_engine() -> Engine:
    global _engine, SessionLocal
    if _engine is None:
        url = database_url()
        if is_sqlite_url(url):
            _engine = create_engine(
                url,
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
        else:
            _engine = create_engine(url, future=True, pool_pre_ping=True)

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
