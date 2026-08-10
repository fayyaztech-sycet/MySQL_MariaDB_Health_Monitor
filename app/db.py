"""SQLAlchemy engine and session factory for the SQLite history database."""
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

_engine = None
_SessionLocal = None

# (table, column, DDL) added to pre-existing tables that lack them.
# create_all only creates new tables; these make existing dev DBs evolve.
_COLUMN_MIGRATIONS = [
    ("system_metrics", "swap_total", "INTEGER"),
]


def _apply_column_migrations(engine) -> None:
    for table, column, ddl in _COLUMN_MIGRATIONS:
        try:
            with engine.begin() as conn:
                cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
                if column not in cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        except Exception:
            # table may not exist yet; create_all handles fresh DBs
            pass


def init_db(sqlite_path: str | None = None) -> None:
    """Create the engine + session factory and ensure tables exist."""
    global _engine, _SessionLocal
    path = sqlite_path or get_settings().sqlite_path
    _engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(_engine)
    _apply_column_migrations(_engine)
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
