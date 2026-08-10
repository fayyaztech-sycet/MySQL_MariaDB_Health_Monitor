"""Query performance ranking from persisted query_stats deltas.

Produces two rankings (README section 4):
  - most expensive queries  (sorted by total_execution_time)
  - worst latency queries   (sorted by avg_execution_time)
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import QueryStats


def _group_stats(session, limit: int = 50) -> list[dict]:
    """Group query_stats deltas by normalized query_text, summing across runs."""
    stmt = (
        select(
            QueryStats.query_text,
            func.sum(QueryStats.calls).label("calls"),
            func.sum(QueryStats.total_ms).label("total_ms"),
            func.sum(QueryStats.rows_examined).label("rows_examined"),
            func.sum(QueryStats.rows_sent).label("rows_sent"),
            func.max(QueryStats.created_at).label("last_seen"),
        )
        .group_by(QueryStats.query_text)
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    result = []
    for r in rows:
        calls = r.calls or 0
        result.append(
            {
                "query": r.query_text,
                "calls": calls,
                "total_ms": round(r.total_ms or 0.0, 2),
                "avg_ms": round((r.total_ms or 0.0) / calls, 2) if calls else 0.0,
                "rows_examined": r.rows_examined or 0,
                "rows_sent": r.rows_sent or 0,
                "last_seen": r.last_seen,
            }
        )
    return result


def most_expensive(session, limit: int = 10) -> list[dict]:
    rows = _group_stats(session)
    rows.sort(key=lambda x: x["total_ms"], reverse=True)
    return rows[:limit]


def worst_latency(session, limit: int = 10) -> list[dict]:
    rows = _group_stats(session)
    rows.sort(key=lambda x: x["avg_ms"], reverse=True)
    return rows[:limit]
