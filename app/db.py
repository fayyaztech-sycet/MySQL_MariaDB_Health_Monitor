"""SQLAlchemy engine and session factory for the SQLite history database."""
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal = None


def _run_migrations(sqlite_path: str) -> None:
    """Apply pending Alembic migrations to the given SQLite file.

    Runs on every app start/restart so the schema always matches the models.
    A pre-Alembic database (tables already present but no ``alembic_version``
    row) is stamped at head as the baseline instead of being re-created.
    """
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{sqlite_path}"
    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)

    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    insp_engine = create_engine(url, connect_args={"timeout": 10})
    try:
        with insp_engine.connect() as insp:
            has_tables = insp.dialect.has_table(insp, "system_metrics")
            if insp.dialect.has_table(insp, "alembic_version"):
                stamped = insp.scalar(text("SELECT version_num FROM alembic_version")) is not None
            else:
                stamped = False

            # Check if we're already at head — skip upgrade (and the write lock) if so.
            if stamped:
                mc = MigrationContext.configure(insp)
                current = mc.get_current_heads()
                script = ScriptDirectory.from_config(cfg)
                head = set(script.get_heads())
                already_at_head = current == head
            else:
                already_at_head = False
    finally:
        insp_engine.dispose()

    if has_tables and not stamped:
        command.stamp(cfg, "head")
    elif not already_at_head:
        command.upgrade(cfg, "head")


def init_db(sqlite_path: str | None = None) -> None:
    """Create the engine + session factory and ensure the schema is current."""
    global _engine, _SessionLocal
    path = sqlite_path or get_settings().sqlite_path
    _engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    _run_migrations(path)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_engine():
    if _engine is None:
        init_db()
    return _engine


def get_session_factory():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context-managed session (commit on success, rollback on error)."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session (no commit)."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
