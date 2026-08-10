"""Slow query collector from performance_schema.events_statements_summary_by_digest.

The server already aggregates by statement digest, so we snapshot cumulative
counters (COUNT_STAR, SUM_TIMER_WAIT, rows) per digest and persist the *delta*
between successive runs into query_stats. This gives per-interval activity.

TIMER_WAIT values in performance_schema are picoseconds; we convert to ms.

The baseline is kept in-memory (module-level). On a fresh process the first run
only establishes the baseline and returns 0 rows; subsequent runs persist deltas.
"""
from __future__ import annotations

from sqlalchemy import select

from app.config import get_settings
from app.mysql_connection import query_all
from app.models import MySqlServer, QueryStats

# digest_text -> (count_star, sum_timer, sum_rows_examined, sum_rows_sent)
_baseline: dict[str, tuple[int, int, int, int]] = {}

SQL = """
SELECT SCHEMA_NAME, DIGEST, DIGEST_TEXT, COUNT_STAR,
       SUM_TIMER_WAIT, AVG_TIMER_WAIT, MAX_TIMER_WAIT,
       SUM_ROWS_EXAMINED, SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST_TEXT IS NOT NULL AND DIGEST_TEXT NOT LIKE '%performance_schema%'
"""


def collect(session, conn) -> int:
    settings = get_settings()
    server = session.scalar(
        select(MySqlServer).where(
            MySqlServer.hostname == settings.mysql_host,
            MySqlServer.port == settings.mysql_port,
        )
    )
    if server is None:
        return 0

    rows = query_all(conn, SQL)
    current: dict[str, tuple[int, int, int, int]] = {}
    for r in rows:
        text = (r["DIGEST_TEXT"] or "").strip()
        if not text:
            continue
        key = text[:1000]
        current[key] = (
            int(r["COUNT_STAR"] or 0),
            int(r["SUM_TIMER_WAIT"] or 0),
            int(r["SUM_ROWS_EXAMINED"] or 0),
            int(r["SUM_ROWS_SENT"] or 0),
        )

    global _baseline
    if not _baseline:
        # First run: establish baseline, nothing to persist.
        _baseline = current
        return 0

    written = 0
    for key, (count, sum_timer, rows_examined, rows_sent) in current.items():
        prev = _baseline.get(key)
        if prev is None:
            continue
        d_count = count - prev[0]
        d_timer = sum_timer - prev[1]
        d_rows_ex = rows_examined - prev[2]
        d_rows_sent = rows_sent - prev[3]
        if d_count <= 0:
            continue

        total_ms = d_timer / 1e9
        avg_ms = total_ms / d_count if d_count else 0.0
        stats = QueryStats(
            server_id=server.id,
            digest=None,
            query_text=key,
            schema_name=None,
            calls=d_count,
            total_ms=total_ms,
            avg_ms=avg_ms,
            max_ms=0.0,
            rows_examined=d_rows_ex,
            rows_sent=d_rows_sent,
        )
        session.add(stats)
        written += 1

    _baseline = current
    session.flush()
    return written
