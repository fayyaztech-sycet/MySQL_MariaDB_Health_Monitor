"""FastAPI routes: JSON API + dashboard HTML pages.

API-key auth is enforced via a header middleware (X-API-Key) on /api/*
endpoints. Dashboard HTML pages are served unauthenticated (for local/dev use).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (
    Alert,
    MySqlServer,
    Recommendation,
    Report,
    SystemMetrics,
    InnoDBMetrics,
    QueryStats,
)

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def require_key(request: Request):
    settings = get_settings()
    token = request.headers.get("X-API-Key", "")
    if settings.api_token != "changeme-token" and token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return None


# --- helpers ---------------------------------------------------------------

def _server(session) -> dict | None:
    row = session.scalar(select(MySqlServer).limit(1))
    if row is None:
        return None
    return {
        "hostname": row.hostname,
        "port": row.port,
        "version": row.version,
        "uptime_seconds": row.uptime_seconds,
        "threads_connected": row.threads_connected,
        "max_connections": row.max_connections,
        "database_size_bytes": row.database_size_bytes,
        "innodb_buffer_pool_size": row.innodb_buffer_pool_size,
    }


def _latest_system(session) -> dict | None:
    row = session.scalar(
        select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(1)
    )
    if row is None:
        return None
    return {
        "cpu": row.cpu,
        "load_avg": row.load_avg,
        "mem_total": row.mem_total,
        "mem_used": row.mem_used,
        "mem_avail": row.mem_avail,
        "disk_used": row.disk_used,
        "disk_total": row.disk_total,
        "net_in": row.net_in,
        "net_out": row.net_out,
        "timestamp": row.timestamp,
    }


def _recent_system(session, limit: int = 200) -> list[dict]:
    rows = session.execute(
        select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "timestamp": r.timestamp,
            "cpu": r.cpu,
            "mem_used": r.mem_used,
            "mem_total": r.mem_total,
            "disk_used": r.disk_used,
            "disk_total": r.disk_total,
            "net_in": r.net_in,
            "net_out": r.net_out,
        }
        for r in reversed(rows)
    ]


# --- JSON API --------------------------------------------------------------

@router.get("/api/overview")
def api_overview(_: None = Depends(require_key), db: Session = Depends(get_db)):
    server = _server(db)
    sys = _latest_system(db)
    slow_count = db.scalar(select(func.count(QueryStats.id)))
    active_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.active == True))  # noqa: E712
    rec_count = db.scalar(select(func.count(Recommendation.id)))
    return {
        "server": server,
        "system": sys,
        "slow_query_records": slow_count,
        "active_alerts": active_alerts,
        "recommendations": rec_count,
    }


@router.get("/api/queries")
def api_queries(limit: int = Query(20), _: None = Depends(require_key),
                db: Session = Depends(get_db)):
    from app.analyzers.query_analyzer import most_expensive, worst_latency
    return {
        "most_expensive": most_expensive(db, limit),
        "worst_latency": worst_latency(db, limit),
    }


@router.get("/api/server-health")
def api_health(_: None = Depends(require_key), db: Session = Depends(get_db)):
    return {"system_metrics": _recent_system(db)}


@router.get("/api/alerts")
def api_alerts(_: None = Depends(require_key), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Alert).order_by(Alert.created_at.desc()).limit(100)
    ).all()
    return [
        {"type": a.type, "severity": a.severity, "message": a.message,
         "value": a.value, "threshold": a.threshold, "active": a.active,
         "created_at": a.created_at}
        for a in rows
    ]


@router.get("/api/recommendations")
def api_recommendations(_: None = Depends(require_key),
                        db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Recommendation).order_by(Recommendation.created_at.desc()).limit(100)
    ).all()
    return [
        {"type": r.type, "title": r.title, "detail": r.detail,
         "sql": r.sql, "severity": r.severity, "created_at": r.created_at}
        for r in rows
    ]


@router.get("/api/reports")
def api_reports(_: None = Depends(require_key), db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).order_by(Report.created_at.desc()).limit(50)).all()
    return [{"filename": r.filename, "health_score": r.health_score,
             "created_at": r.created_at} for r in rows]


# --- Dashboard HTML ---------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    server = _server(db)
    sys = _latest_system(db)
    active_alerts = db.scalars(
        select(Alert).where(Alert.active == True).order_by(Alert.created_at.desc())  # noqa: E712
    ).all()
    recs = db.scalars(
        select(Recommendation).order_by(Recommendation.created_at.desc()).limit(5)
    ).all()
    cpu_json = _recent_system(db)[-60:]
    from app.reports.charts import line_timeseries, bar_ranking

    chart = line_timeseries(cpu_json, "timestamp", [("CPU %", "cpu")], "CPU Usage")
    return templates.TemplateResponse(
        request, "overview.html",
        {"server": server, "system": sys, "alerts": active_alerts,
         "recommendations": recs, "cpu_chart": chart},
    )


@router.get("/dashboard/queries", response_class=HTMLResponse)
def dashboard_queries(request: Request, db: Session = Depends(get_db)):
    from app.analyzers.query_analyzer import most_expensive, worst_latency
    from app.reports.charts import bar_ranking
    expensive = most_expensive(db, 15)
    latency = worst_latency(db, 15)
    chart = bar_ranking(expensive, "query", "total_ms", "Most Expensive Queries (ms)")
    return templates.TemplateResponse(
        request, "queries.html",
        {"expensive": expensive, "latency": latency, "chart": chart},
    )


@router.get("/dashboard/health", response_class=HTMLResponse)
def dashboard_health(request: Request, db: Session = Depends(get_db)):
    from app.reports.charts import line_timeseries
    rows = _recent_system(db, 500)
    charts = {
        "cpu": line_timeseries(rows, "timestamp", [("CPU %", "cpu")], "CPU"),
        "memory": line_timeseries(rows, "timestamp", [("Used", "mem_used")], "RAM Used (bytes)"),
        "disk": line_timeseries(rows, "timestamp", [("Used", "disk_used")], "Disk Used (bytes)"),
        "network": line_timeseries(rows, "timestamp", [("In", "net_in"), ("Out", "net_out")], "Network"),
    }
    return templates.TemplateResponse(request, "health.html", {"charts": charts})
