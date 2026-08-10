"""Daily HTML report generator (README section 13).

Produces reports/mysql-report-YYYY-MM-DD.html with a health score, problem
summary, recommendations, and charts. Registers a Report row on success.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.config import get_settings
from app.models import (
    Alert,
    InnoDBMetrics,
    MySqlServer,
    Recommendation,
    Report,
    SystemMetrics,
)

logger = logging.getLogger(__name__)


def compute_health_score(session) -> tuple[int, list[str]]:
    """Heuristic 0-100 health score with a list of deductions for the report."""
    score = 100
    problems: list[str] = []

    latest = session.scalar(
        select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(1)
    )
    if latest is not None:
        if latest.cpu > 90:
            score -= 15
            problems.append(f"CPU at {latest.cpu:.1f}%")
        if latest.mem_total and latest.mem_avail / latest.mem_total * 100 < 10:
            score -= 10
            problems.append("Available RAM below 10%")
        if latest.disk_total and latest.disk_used / latest.disk_total * 100 > 90:
            score -= 10
            problems.append("Disk usage above 90%")

    innodb = session.scalar(
        select(InnoDBMetrics).order_by(InnoDBMetrics.timestamp.desc()).limit(1)
    )
    if innodb is not None and innodb.deadlocks > 0:
        score -= 15
        problems.append("InnoDB deadlock detected")

    slow_count = session.scalar(select(func.count(Alert.id)).where(Alert.type == "slow_query"))
    if slow_count:
        score -= min(slow_count * 5, 25)
        problems.append(f"{slow_count} slow queries detected")

    server = session.scalar(select(MySqlServer).limit(1))
    if server is not None:
        from app.analyzers.memory_analyzer import estimate
        mem = estimate(server)
        if mem["risk"] == "high":
            score -= 15
            problems.append("High memory pressure")
        elif mem["risk"] == "medium":
            score -= 5

    index_count = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.type == "index")
    )
    if index_count:
        score -= min(index_count * 5, 20)
        problems.append(f"{index_count} missing indexes suggested")

    return max(score, 0), problems


def generate(session) -> str | None:
    """Build the report file; returns the filename or None on failure."""
    settings = get_settings()
    score, problems = compute_health_score(session)

    recs = session.scalars(
        select(Recommendation).order_by(Recommendation.created_at.desc()).limit(20)
    ).all()
    server = session.scalar(select(MySqlServer).limit(1))
    slow = session.scalars(
        select(Alert).where(Alert.type == "slow_query")
        .order_by(Alert.created_at.desc()).limit(10)
    ).all()

    recent_objs = session.execute(
        select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(200)
    ).scalars().all()
    recent = [
        {"timestamp": r.timestamp, "cpu": r.cpu, "mem_used": r.mem_used,
         "disk_used": r.disk_used}
        for r in reversed(recent_objs)
    ]

    from app.reports.charts import health_gauge, line_timeseries
    gauge = health_gauge(score)
    cpu_chart = line_timeseries(recent, "timestamp", [("CPU %", "cpu")], "CPU Usage")
    mem_chart = line_timeseries(recent, "timestamp", [("Used", "mem_used")], "RAM Used")

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    filename = f"mysql-report-{date_str}.html"
    out_dir = Path(settings.report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    template = _REPORT_TEMPLATE.format(
        date=date_str,
        score=score,
        problems="; ".join(problems) if problems else "No critical problems detected.",
        hostname=(server.hostname if server else "n/a"),
        version=(server.version or "n/a") if server else "n/a",
        cpu_chart=cpu_chart,
        mem_chart=mem_chart,
        gauge=gauge,
    )
    out_path.write_text(template, encoding="utf-8")

    session.add(Report(filename=filename, health_score=score))
    session.flush()
    logger.info("report generated: %s (score %d)", filename, score)
    return filename


_REPORT_TEMPLATE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>MySQL Report {date}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
 body {{ font-family: system-ui,sans-serif; margin:0; background:#f5f6f8; }}
 .wrap {{ max-width: 900px; margin: 1.5rem auto; padding: 0 1rem; }}
 h1 {{ font-size:1.4rem; }} .panel {{ background:#fff; border-radius:8px; padding:1rem;
   margin:1rem 0; box-shadow:0 1px 3px rgba(0,0,0,.1); }}
 .score {{ font-size:2.2rem; font-weight:800; }}
 table {{ width:100%%; border-collapse:collapse; font-size:.9rem; }}
 th,td {{ text-align:left; padding:.4rem .6rem; border-bottom:1px solid #eee; }}
</style></head><body><div class="wrap">
<h1>MySQL Performance Report — {date}</h1>
<div class="panel"><h2>Database Health Score</h2>
<div class="score">{score}/100</div><p>{problems}</p>
<div id="gauge"></div></div>
<div class="panel"><h2>Server</h2>
<p><b>Host:</b> {hostname} &nbsp; <b>Version:</b> {version}</p></div>
<div class="panel"><h2>CPU Usage</h2><div id="cpu"></div></div>
<div class="panel"><h2>RAM Used</h2><div id="mem"></div></div>
<div class="panel"><h2>Recommendations</h2>
<table><tr><th>Severity</th><th>Type</th><th>Title</th><th>SQL</th></tr>
<tr><td colspan="4">(Recommendations are stored in the app; see dashboard)</td></tr>
</table></div>
<script>
 const g={{ gauge }}; Plotly.newPlot('gauge',g.data,g.layout,{{}});
 const c={{ cpu_chart }}; Plotly.newPlot('cpu',c.data,c.layout,{{}});
 const m={{ mem_chart }}; Plotly.newPlot('mem',m.data,m.layout,{{}});
</script>
</div></body></html>"""
