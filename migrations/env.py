"""Alembic migration environment, bound to the app's SQLAlchemy metadata.

The DB URL is taken from the ``sqlalchemy.url`` main option, which the
startup runner (``app/db.py``) sets programmatically from app settings so
migrations always target the same SQLite file the app uses.
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config import get_settings
from app.models import Base

config = context.config

# When invoked from the CLI (e.g. ``alembic revision --autogenerate``) the URL
# may be unset; fall back to the app's configured SQLite path so autogen diffs
# against the real database file. Programmatic runs (startup runner in
# app/db.py) always set it explicitly, overriding this default.
if config.get_main_option("sqlalchemy.url") is None:
    config.set_main_option("sqlalchemy.url", get_settings().sqlite_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Bind to the app's metadata so ``alembic revision --autogenerate`` (and the
# startup runner) can diff against the real schema.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # render_as_batch gives SQLite support for ALTER TABLE operations.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
