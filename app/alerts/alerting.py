"""Alert rules evaluator (README section 10).

Rules:
  - High CPU            cpu > alert_cpu_high
  - Low available RAM   avail_ram% < alert_mem_avail_low
  - High disk           disk_used% > alert_disk_high
  - Slow query          a query avg_ms > alert_slow_query_ms
  - Deadlock            innodb deadlocks > 0

Only fires when no *active* alert of the same type exists (dedupe).
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.config import get_settings
from app.models import Alert, InnoDBMetrics, MySqlServer, QueryStats, SystemMetrics

logger = logging.getLogger(__name__)


def _active_types(session) -> set[str]:
    rows = session.execute(
        select(Alert.type).where(Alert.active == True)  # noqa: E712
    ).all()
    return {r[0] for r in rows}


def _fire(session, active: set[str], type_: str, message: str,
          value: float, threshold: float, severity: str = "warning") -> int:
    if type_ in active:
        return 0
    session.add(Alert(type=type_, message=message, value=value,
                      threshold=threshold, severity=severity, active=True))
    active.add(type_)
    return 1


def evaluate(session, conn) -> int:
    settings = get_settings()
    active = _active_types(session)
    fired = 0

    # CPU / RAM / disk from the latest system metric
    latest = session.scalar(
        select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(1)
    )
    if latest is not None:
        if latest.cpu > settings.alert_cpu_high:
            fired += _fire(session, active, "cpu_high",
                           f"CPU at {latest.cpu:.1f}% (>{settings.alert_cpu_high}%)",
                           latest.cpu, settings.alert_cpu_high, "critical")
        if latest.mem_total:
            avail_pct = latest.mem_avail / latest.mem_total * 100
            if avail_pct < settings.alert_mem_avail_low:
                fired += _fire(session, active, "memory_low",
                               f"Available RAM {avail_pct:.1f}% (<{settings.alert_mem_avail_low}%)",
                               avail_pct, settings.alert_mem_avail_low, "warning")
        if latest.disk_total:
            disk_pct = latest.disk_used / latest.disk_total * 100
            if disk_pct > settings.alert_disk_high:
                fired += _fire(session, active, "disk_high",
                               f"Disk {disk_pct:.1f}% used (>{settings.alert_disk_high}%)",
                               disk_pct, settings.alert_disk_high, "warning")

    # Deadlock
    innodb = session.scalar(
        select(InnoDBMetrics).order_by(InnoDBMetrics.timestamp.desc()).limit(1)
    )
    if innodb is not None and innodb.deadlocks >= settings.alert_deadlock_trigger:
        fired += _fire(session, active, "deadlock",
                       "InnoDB deadlock detected", innodb.deadlocks,
                       settings.alert_deadlock_trigger, "critical")

    # Slow queries from recent window (last 5 minutes)
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(minutes=5)
    slow = session.execute(
        select(QueryStats.query_text, func.avg(QueryStats.avg_ms).label("avg"))
        .where(QueryStats.created_at >= since)
        .group_by(QueryStats.query_text)
        .having(func.avg(QueryStats.avg_ms) > settings.alert_slow_query_ms)
        .limit(5)
    ).all()
    for row in slow:
        avg = row.avg or 0.0
        fired += _fire(session, active, "slow_query",
                       f"Slow query avg {avg / 1000:.1f}s: {row.query_text[:120]}",
                       avg, settings.alert_slow_query_ms, "warning")

    session.flush()
    return fired
