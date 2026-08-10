"""MySQL status collector: server version, connections, thread counts, buffer
pool, database/table sizes. Upserts the mysql_servers row.
"""
from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.mysql_connection import query_all
from app.models import MySqlServer


def _status_map(conn) -> dict:
    rows = query_all(conn, "SHOW GLOBAL STATUS")
    return {r["Variable_name"]: r["Value"] for r in rows}


def _variable(conn, name: str) -> str:
    rows = query_all(conn, "SHOW GLOBAL VARIABLES LIKE %s", (name,))
    return rows[0]["Value"] if rows else ""


def collect(session, conn) -> int:
    settings = get_settings()

    # Version
    version = ""
    try:
        vrows = query_all(conn, "SELECT VERSION() AS v")
        version = str(vrows[0]["v"]) if vrows else ""
    except Exception:
        version = ""

    status = _status_map(conn)
    threads = _int(status.get("Threads_connected"))
    uptime = _int(status.get("Uptime"))

    max_conn = _int(_variable(conn, "max_connections")) or 151
    buffer_pool = _int(_variable(conn, "innodb_buffer_pool_size"))

    # Database size across information_schema.tables (bytes)
    db_size = 0
    try:
        size_rows = query_all(
            conn,
            "SELECT COALESCE(SUM(data_length + index_length),0) AS sz "
            "FROM information_schema.tables WHERE table_schema NOT IN "
            "('information_schema','performance_schema','mysql','sys')",
        )
        if size_rows:
            db_size = _int(size_rows[0]["sz"])
    except Exception:
        db_size = 0

    host, port = settings.mysql_host, settings.mysql_port
    server = session.scalar(
        select(MySqlServer).where(
            MySqlServer.hostname == host, MySqlServer.port == port
        )
    )
    if server is None:
        server = MySqlServer(hostname=host, port=port)
        session.add(server)
        session.flush()

    server.version = version or server.version
    server.uptime_seconds = uptime
    server.threads_connected = threads
    server.max_connections = max_conn
    server.database_size_bytes = db_size
    server.innodb_buffer_pool_size = buffer_pool

    session.flush()
    return 1


def _int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
