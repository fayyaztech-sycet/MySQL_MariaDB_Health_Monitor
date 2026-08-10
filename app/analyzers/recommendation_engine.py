"""Rule-based recommendation engine (README sections 6 & 16, deferred AI).

Aggregates analyzer findings into Recommendation rows. Deduplicates against
recent recommendations so the store doesn't flood with identical advice.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select

from app.analyzers import index_analyzer, memory_analyzer, query_analyzer
from app.models import MySqlServer, Recommendation

logger = logging.getLogger(__name__)

_LOOKBACK_HOURS = 24


def _recent_titles(session) -> set[str]:
    since = func.now() - timedelta(hours=_LOOKBACK_HOURS)
    rows = session.execute(
        select(Recommendation.title).where(Recommendation.created_at >= since)
    ).all()
    return {r[0] for r in rows}


def _add(session, recent: set[str], type_: str, title: str, detail: str,
         sql: str | None = None, severity: str = "info") -> int:
    if title in recent:
        return 0
    session.add(Recommendation(type=type_, title=title, detail=detail,
                               sql=sql, severity=severity))
    recent.add(title)
    return 1


def run(session, conn) -> int:
    recent = _recent_titles(session)
    added = 0

    server = session.scalar(select(MySqlServer).limit(1))
    if server is not None:
        mem = memory_analyzer.estimate(server)
        if mem["risk"] in ("high", "medium"):
            added += _add(
                session, recent, "memory", f"Memory pressure detected ({mem['risk']})",
                (f"Estimated MySQL usage {mem['estimated_gb']} GB vs {mem['ram_gb']} GB RAM "
                 f"({int(mem['ratio'] * 100)}%). Consider raising innodb_buffer_pool_size "
                 f"and tuning per-connection buffers."),
                sql="SET GLOBAL innodb_buffer_pool_size = ...;",
                severity="warning" if mem["risk"] == "high" else "info",
            )

    expensive = query_analyzer.most_expensive(session, limit=5)
    if expensive:
        top = expensive[0]
        added += _add(
            session, recent, "query", "High-cost query detected",
            (f"'{top['query'][:120]}' consumed {top['total_ms'] / 1000:.1f}s total "
             f"across {top['calls']} calls."),
            severity="info",
        )

    # EXPLAIN-based index suggestions (best-effort)
    try:
        findings = index_analyzer.analyze_queries(session, conn, expensive, limit=5)
    except Exception:
        logger.exception("index analysis failed")
        findings = []

    for f in findings:
        if f["type"] in ("full_table_scan", "missing_index"):
            title = f"Index needed on {f.get('table', '?')}"
            added += _add(
                session, recent, "index", title, f["detail"],
                sql=f"CREATE INDEX idx_{f.get('table', 'col')} ON {f.get('table', '?')}(col);",
                severity="warning",
            )

    session.flush()
    return added
