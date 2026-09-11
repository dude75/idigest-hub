"""SQLAlchemy engine и сессии. SQLite из коробки, схема под PostgreSQL."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from pathlib import Path
from urllib.parse import unquote

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

log = logging.getLogger("app")
_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
_SQLITE_BUSY_TIMEOUT_SEC = 30.0
_POSTGRES_CONNECT_TIMEOUT_SEC = 10
_POSTGRES_STARTUP_RETRIES = 60
_POSTGRES_STARTUP_RETRY_SEC = 1.0


def sqlite_url(path: str) -> str:
    resolved = Path(path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved}"


def resolve_database_url(url: str, *, data_dir: str = "./data") -> str:
    parsed = make_url(url)
    if parsed.drivername != "sqlite":
        query = dict(parsed.query)
        query.setdefault("connect_timeout", str(_POSTGRES_CONNECT_TIMEOUT_SEC))
        return parsed.set(query=query).render_as_string(hide_password=False)

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


def _table_columns(conn, table: str, *, engine: Engine) -> set[str]:
    if is_sqlite_engine(engine):
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    # Use the active connection; inspect(engine) opens another one and can deadlock
    # PostgreSQL DDL/metadata checks inside engine.begin().
    table_insp = inspect(conn)
    if not table_insp.has_table(table):
        return set()
    return {column["name"] for column in table_insp.get_columns(table)}


def _alembic_config() -> Config:
    return Config(str(_ALEMBIC_INI))


def _has_alembic_version(engine: Engine) -> bool:
    return inspect(engine).has_table("alembic_version")


def _has_app_schema(engine: Engine) -> bool:
    return inspect(engine).has_table("users")


def _bootstrap_alembic(engine: Engine) -> None:
    if _has_alembic_version(engine):
        return
    if _has_app_schema(engine):
        _startup_log("database init: legacy schema without alembic_version, stamping head")
        command.stamp(_alembic_config(), "head")


def _run_alembic_upgrade() -> None:
    command.upgrade(_alembic_config(), "head")


def _fk_on_delete(conn, table: str, column: str, *, engine: Engine) -> str | None:
    if is_sqlite_engine(engine):
        rows = conn.exec_driver_sql(f"PRAGMA foreign_key_list({table})").fetchall()
        for row in rows:
            if row[3] == column:
                return (row[6] or "").upper()
        return None

    table_insp = inspect(conn)
    for fk in table_insp.get_foreign_keys(table):
        if column in fk["constrained_columns"]:
            ondelete = (fk.get("options") or {}).get("ondelete")
            return (ondelete or "").upper() if ondelete else None
    return None


def _task_produced_fks_ok(conn, *, engine: Engine) -> bool:
    for column in ("produced_transcript_id", "produced_summary_id"):
        if _fk_on_delete(conn, "tasks", column, engine=engine) != "SET NULL":
            return False
    return True


def _usage_events_references_tasks_old(conn) -> bool:
    table_insp = inspect(conn)
    if not table_insp.has_table("usage_events"):
        return False
    rows = conn.exec_driver_sql("PRAGMA foreign_key_list(usage_events)").fetchall()
    return any(row[2] == "tasks_old" for row in rows)


def _sqlite_recreate_table_from_model(conn, model_cls) -> None:
    table = model_cls.__table__
    bind = conn.get_bind()
    name = table.name
    columns = [col["name"] for col in inspect(conn).get_columns(name)]
    quoted = ", ".join(columns)
    conn.exec_driver_sql(f"ALTER TABLE {name} RENAME TO {name}_old")
    for index in table.indexes:
        conn.exec_driver_sql(f"DROP INDEX IF EXISTS {index.name}")
    table.create(bind)
    conn.exec_driver_sql(f"INSERT INTO {name} ({quoted}) SELECT {quoted} FROM {name}_old")
    conn.exec_driver_sql(f"DROP TABLE {name}_old")


def _sqlite_fix_task_produced_fks(conn) -> None:
    """Recreate tasks and usage_events; renaming tasks breaks usage_events.task_id FK on SQLite."""
    from app.models import Task, UsageEvent

    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    _sqlite_recreate_table_from_model(conn, Task)
    if inspect(conn).has_table("usage_events"):
        _sqlite_recreate_table_from_model(conn, UsageEvent)
    conn.exec_driver_sql("PRAGMA foreign_keys=ON")


def _apply_task_produced_fk_patch(conn, *, engine: Engine) -> None:
    if not _table_columns(conn, "tasks", engine=engine):
        return

    if is_sqlite_engine(engine):
        needs_task_fix = not _task_produced_fks_ok(conn, engine=engine)
        needs_usage_fix = _usage_events_references_tasks_old(conn)
        if not needs_task_fix and not needs_usage_fix:
            return
        if needs_task_fix:
            _sqlite_fix_task_produced_fks(conn)
            return
        from app.models import UsageEvent

        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        _sqlite_recreate_table_from_model(conn, UsageEvent)
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        return

    if _task_produced_fks_ok(conn, engine=engine):
        return

    conn.exec_driver_sql(
        "ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_produced_transcript_id_fkey"
    )
    conn.exec_driver_sql(
        "ALTER TABLE tasks ADD CONSTRAINT tasks_produced_transcript_id_fkey "
        "FOREIGN KEY (produced_transcript_id) REFERENCES transcripts (id) ON DELETE SET NULL"
    )
    conn.exec_driver_sql(
        "ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_produced_summary_id_fkey"
    )
    conn.exec_driver_sql(
        "ALTER TABLE tasks ADD CONSTRAINT tasks_produced_summary_id_fkey "
        "FOREIGN KEY (produced_summary_id) REFERENCES summaries (id) ON DELETE SET NULL"
    )


def _ensure_task_produced_fk_on_delete_set_null(engine: Engine) -> None:
    with engine.begin() as conn:
        _apply_task_produced_fk_patch(conn, engine=engine)


def _apply_idempotent_patches(engine: Engine) -> None:
    """Non-column fixes that legacy ensure_schema() never applied."""
    _ensure_task_produced_fk_on_delete_set_null(engine)


def _startup_log(message: str) -> None:
    print(f"idigest-hub: {message}", flush=True)
    log.info(message)


def _wait_for_database(engine: Engine) -> None:
    if is_sqlite_engine(engine):
        return
    last_error: Exception | None = None
    for attempt in range(1, _POSTGRES_STARTUP_RETRIES + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if attempt > 1:
                _startup_log(f"database init: postgres ready after {attempt} attempts")
            return
        except Exception as exc:
            last_error = exc
            _startup_log(
                f"database init: waiting for postgres ({attempt}/{_POSTGRES_STARTUP_RETRIES}): {exc}"
            )
            time.sleep(_POSTGRES_STARTUP_RETRY_SEC)
    raise RuntimeError("PostgreSQL did not become ready during startup") from last_error


def init_database(engine: Engine) -> None:
    """Wait for DB, run Alembic migrations, apply idempotent schema patches."""
    _startup_log("database init: begin")
    _wait_for_database(engine)
    _bootstrap_alembic(engine)
    _startup_log("database init: alembic upgrade")
    _run_alembic_upgrade()
    _startup_log("database init: schema patches")
    _apply_idempotent_patches(engine)
    _startup_log("database init: done")


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
            _engine = create_engine(
                url,
                future=True,
                pool_pre_ping=True,
                connect_args={"connect_timeout": _POSTGRES_CONNECT_TIMEOUT_SEC},
            )

            @event.listens_for(_engine, "connect")
            def _pg_session_limits(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
                cursor = dbapi_connection.cursor()
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SET statement_timeout = '120s'")
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
