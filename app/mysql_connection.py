"""MySQL connection helper used by the DB collectors.

Collectors receive a live mysql.connector connection. This module wraps the
settings kwargs and connection lifecycle so tests can inject a stub/fake.
"""
from __future__ import annotations

from typing import Any, Optional

import mysql.connector
from mysql.connector import MySQLConnection

from app.config import get_settings


def connect(**overrides: Any) -> MySQLConnection:
    """Open a connection to the monitored MySQL server."""
    kwargs = get_settings().mysql_connector_kwargs
    kwargs.update(overrides)
    return mysql.connector.connect(**kwargs)


def query_all(conn: MySQLConnection, sql: str, params: tuple | None = None) -> list[dict]:
    """Run a query and return rows as dicts."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    finally:
        cur.close()


def query_one(conn: MySQLConnection, sql: str, params: tuple | None = None) -> Optional[dict]:
    rows = query_all(conn, sql, params)
    return rows[0] if rows else None
