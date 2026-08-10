"""Process collector: SHOW PROCESSLIST summary + mysqld/mariadbd process stats.

Stores a ProcessMetrics row for the MySQL daemon process and tracks query
state counts. State counts are logged but primarily the daemon metrics are
persisted (per the README section 9).
"""
from __future__ import annotations

import psutil

from app.mysql_connection import query_all
from app.models import ProcessMetrics

DAEMON_NAMES = {"mysqld", "mariadbd"}


def _find_daemon():
    for proc in psutil.process_iter(["name", "cpu_percent", "memory_info", "num_threads"]):
        name = (proc.info.get("name") or "").lower()
        if name in DAEMON_NAMES:
            try:
                mem = proc.info.get("memory_info")
                rss = mem.rss if mem else 0
            except Exception:
                rss = 0
            open_files = 0
            try:
                open_files = len(proc.open_files())
            except Exception:
                open_files = 0
            return {
                "name": proc.info.get("name"),
                "cpu_percent": proc.info.get("cpu_percent") or 0.0,
                "memory_rss": rss,
                "threads": proc.info.get("num_threads") or 0,
                "open_files": open_files,
            }
    return None


def collect(session, conn) -> int:
    rows_written = 0

    # Summarize process list by state (informational / for alerting)
    try:
        plist = query_all(conn, "SHOW PROCESSLIST")
        state_counts: dict = {}
        for row in plist:
            state = row.get("State") or "Sleeping"
            state_counts[state] = state_counts.get(state, 0) + 1
    except Exception:
        state_counts = {}

    daemon = _find_daemon()
    if daemon:
        row = ProcessMetrics(
            process_name=daemon["name"],
            cpu_percent=daemon["cpu_percent"],
            memory_rss=daemon["memory_rss"],
            threads=daemon["threads"],
            open_files=daemon["open_files"],
        )
        session.add(row)
        session.flush()
        rows_written += 1

    return rows_written
