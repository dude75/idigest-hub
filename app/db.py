"""SQLAlchemy engine и сессии. SQLite из коробки, схема под PostgreSQL."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import create_engine, event, inspect
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


def _table_columns(conn, table: str, *, engine: Engine) -> set[str]:
    if is_sqlite_engine(engine):
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    if not inspect(engine).has_table(table):
        return set()
    return {column["name"] for column in inspect(engine).get_columns(table)}


def _try_drop_column(conn, table: str, column: str) -> None:
    try:
        conn.exec_driver_sql(f"ALTER TABLE {table} DROP COLUMN {column}")
    except Exception:
        pass


def ensure_schema(engine: Engine) -> None:
    """Patches for upgrades without Alembic; create_all skips new columns on existing tables."""
    sqlite = is_sqlite_engine(engine)
    bool_false = "0" if sqlite else "false"
    bool_true = "1" if sqlite else "true"

    with engine.begin() as conn:
        user_cols = _table_columns(conn, "users", engine=engine)
        if user_cols and "default_route" not in user_cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN default_route VARCHAR(32) NOT NULL DEFAULT 'library/audio'"
            )
        user_cols = _table_columns(conn, "users", engine=engine)
        if user_cols and "default_route" in user_cols:
            conn.exec_driver_sql(
                "UPDATE users SET default_route='library/audio' WHERE default_route='library'"
            )

        summary_cols = _table_columns(conn, "summaries", engine=engine)
        if summary_cols and "edited" not in summary_cols:
            conn.exec_driver_sql(
                f"ALTER TABLE summaries ADD COLUMN edited BOOLEAN NOT NULL DEFAULT {bool_false}"
            )

        tariff_cols = _table_columns(conn, "tariffs", engine=engine)
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
                    f"ALTER TABLE tariffs ADD COLUMN api_enabled BOOLEAN NOT NULL DEFAULT {bool_true}"
                )
            if "signup_credit" not in tariff_cols:
                conn.exec_driver_sql(
                    "ALTER TABLE tariffs ADD COLUMN signup_credit NUMERIC(12, 2) NOT NULL DEFAULT 0"
                )
            if "price_per_generated_text" in _table_columns(conn, "tariffs", engine=engine):
                _try_drop_column(conn, "tariffs", "price_per_generated_text")

        task_cols = _table_columns(conn, "tasks", engine=engine)
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
            if "snap_price_per_generated_text" in _table_columns(conn, "tasks", engine=engine):
                _try_drop_column(conn, "tasks", "snap_price_per_generated_text")

        usage_cols = _table_columns(conn, "usage_events", engine=engine)
        if usage_cols and "summary_chars" not in usage_cols:
            conn.exec_driver_sql("ALTER TABLE usage_events ADD COLUMN summary_chars INTEGER")

        settings_cols = _table_columns(conn, "instance_settings", engine=engine)
        if settings_cols:
            _instance_rate_limit_patches(conn, settings_cols, engine=engine)


def _add_int_column(conn, table: str, column: str, default: int, *, engine: Engine) -> None:
    cols = _table_columns(conn, table, engine=engine)
    if column not in cols:
        conn.exec_driver_sql(
            f"ALTER TABLE {table} ADD COLUMN {column} INTEGER NOT NULL DEFAULT {default}"
        )


def _add_bool_column(conn, table: str, column: str, default: int, *, engine: Engine) -> None:
    cols = _table_columns(conn, table, engine=engine)
    if column not in cols:
        if is_sqlite_engine(engine):
            sql_default = str(default)
        else:
            sql_default = "true" if default else "false"
        conn.exec_driver_sql(
            f"ALTER TABLE {table} ADD COLUMN {column} BOOLEAN NOT NULL DEFAULT {sql_default}"
        )


def _instance_rate_limit_patches(conn, settings_cols: set[str], *, engine: Engine) -> None:
    if "rate_limit_enabled" not in settings_cols:
        _add_bool_column(conn, "instance_settings", "rate_limit_enabled", 1, engine=engine)
    patches = (
        ("rate_limit_login_email", 30),
        ("rate_limit_login_ip", 0),
        ("rate_limit_login_global", 500),
        ("rate_limit_signup_email", 10),
        ("rate_limit_signup_ip", 0),
        ("rate_limit_signup_global", 100),
        ("rate_limit_reset_email", 10),
        ("rate_limit_reset_ip", 0),
        ("rate_limit_reset_global", 50),
        ("rate_limit_reset_confirm_ip", 0),
        ("rate_limit_reset_confirm_global", 100),
        ("rate_limit_setup_ip", 0),
        ("rate_limit_setup_global", 10),
        ("rate_limit_api_user", 120),
        ("rate_limit_api_ip", 0),
        ("rate_limit_api_global", 2000),
        ("rate_limit_api_tasks_user", 30),
        ("rate_limit_api_tasks_ip", 0),
    )
    for column, default in patches:
        _add_int_column(conn, "instance_settings", column, default, engine=engine)


def run_alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url())
    command.upgrade(cfg, "head")


def init_database(engine: Engine) -> None:
    """Create tables and apply incremental schema updates."""
    from app.models import Base

    if is_sqlite_engine(engine):
        Base.metadata.create_all(engine)
        ensure_schema(engine)
        return

    inspector = inspect(engine)
    if inspector.has_table("alembic_version"):
        run_alembic_upgrade()
    Base.metadata.create_all(engine)
    ensure_schema(engine)


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
