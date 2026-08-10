"""Shared test fixtures: an isolated temp SQLite DB and a fake MySQL connection."""
from __future__ import annotations

import tempfile
from datetime import datetime

import pytest

from app.db import init_db, session_scope
from app.models import Base


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    yield path


@pytest.fixture()
def session(db_path):
    with session_scope() as s:
        yield s


class FakeCursor:
    """Returns rows selected by the SQL statement, mimicking the real cursor.

    ``router`` is a callable(sql, params) -> list[dict]. If no rows are
    matched it returns [] so queries behave as "empty".
    """

    def __init__(self, router):
        self._router = router
        self._rows: list[dict] = []

    def execute(self, sql, params=None):
        self._rows = self._router(sql, params or ()) if self._router else []

    def fetchall(self):
        return list(self._rows)

    def close(self):
        return None


class FakeConn:
    """A stand-in MySQL connection.

    ``routes`` may be a dict mapping a SQL keyword (substring, case-insensitive)
    to rows, OR a callable router(sql, params) -> rows.
    """

    def __init__(self, routes):
        self._routes = routes
        self._router = routes if callable(routes) else self._keyword_router

    def _keyword_router(self, sql: str, params=()):  # noqa: ARG002
        lowered = sql.lower()
        for key, rows in self._routes.items():
            if key.lower() in lowered:
                return rows
        return []

    def cursor(self, dictionary=True):  # noqa: ARG002
        return FakeCursor(self._router)

    def close(self):
        return None
