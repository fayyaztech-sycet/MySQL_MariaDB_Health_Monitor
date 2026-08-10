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

    insp_engine = create_engine(url)
    try:
        with insp_engine.connect() as insp:
            has_tables = insp.dialect.has_table(insp, "system_metrics")
            if insp.dialect.has_table(insp, "alembic_version"):
                # The table can exist (e.g. after a bare autogenerate run) with
                # no revision recorded; only a stamped row counts as versioned.
                stamped = insp.scalar(text("SELECT version_num FROM alembic_version")) is not None
            else:
                stamped = False
    finally:
        insp_engine.dispose()

    if has_tables and not stamped:
        # Legacy database created before Alembic: its schema already matches
        # the initial revision, so record it as up-to-date rather than failing
        # on "table already exists".
        command.stamp(cfg, "head")
    else:
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
