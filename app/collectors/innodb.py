"""InnoDB health collector: parses SHOW ENGINE INNODB STATUS output.

Monitors buffer pool hit ratio, dirty pages, pending I/O, history list length,
and deadlock presence (README section 7).
"""
from __future__ import annotations

import re

from app.mysql_connection import query_all
from app.models import InnoDBMetrics


def _fetch_status(conn) -> str:
    rows = query_all(conn, "SHOW ENGINE INNODB STATUS")
    if not rows:
        return ""
    return rows[0].get("Status") or ""


def parse_status(text: str) -> dict:
    """Parse INNODB STATUS free-text into numeric metrics."""
    hit_ratio = 0.0
    m = re.search(r"Buffer pool hit rate (\d+)\s*/\s*1000", text)
    if m:
        hit_ratio = round(int(m.group(1)) / 10.0, 1)

    history = 0
    m = re.search(r"History list length (\d+)", text)
    if m:
        history = int(m.group(1))

    dirty = 0
    m = re.search(r"Modified db pages (\d+)", text)
    if m:
        dirty = int(m.group(1))

    pending = 0
    m = re.search(r"Pending writes:\s*(\d+)", text)
    if m:
        pending = int(m.group(1))

    deadlocks = 1 if "LATEST DETECTED DEADLOCK" in text else 0

    return {
        "buffer_hit_ratio": hit_ratio,
        "deadlocks": deadlocks,
        "dirty_pages": dirty,
        "pending_io": pending,
        "history_list_len": history,
    }


def collect(session, conn) -> int:
    text = _fetch_status(conn)
    if not text:
        return 0
    metrics = parse_status(text)
    row = InnoDBMetrics(**metrics)
    session.add(row)
    session.flush()
    return 1
