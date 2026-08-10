"""FastAPI routes: JSON API + dashboard pages.

Main dashboard (/) is a single page with all graphs, updated live over a
WebSocket. The /logs page lists alerts with a date-range filter and a Live
toggle. JSON endpoints under /api/* accept API-key auth.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, get_session_factory
from app.models import (
    Alert,
    MySqlServer,
    Recommendation,
    Report,
    SystemMetrics,
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


# --- snapshot helpers (shared by initial render + WebSocket) -----------------

def _server(db: Session) -> dict | None:
    row = db.scalar(select(MySqlServer).limit(1))
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


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _latest_system(db: Session) -> dict | None:
    row = db.scalar(select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(1))
    if row is None:
        return None
    return {
        "timestamp": _iso(row.timestamp),
        "cpu": row.cpu,
        "load_avg": row.load_avg,
        "mem_total": row.mem_total,
        "mem_used": row.mem_used,
        "mem_avail": row.mem_avail,
        "disk_used": row.disk_used,
        "disk_total": row.disk_total,
        "net_in": row.net_in,
        "net_out": row.net_out,
    }


def _recent_system(db: Session, limit: int = 120) -> list[dict]:
    rows = db.execute(
        select(SystemMetrics).order_by(SystemMetrics.timestamp.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "timestamp": _iso(r.timestamp),
            "cpu": r.cpu,
            "mem_used": r.mem_used,
            "mem_total": r.mem_total,
            "mem_pct": round(r.mem_used / r.mem_total * 100, 1) if r.mem_total else 0.0,
            "swap_pct": round(r.swap_used / r.swap_total * 100, 1) if r.swap_total else 0.0,
            "disk_used": r.disk_used,
            "disk_total": r.disk_total,
            "disk_pct": round(r.disk_used / r.disk_total * 100, 1) if r.disk_total else 0.0,
            "net_in": r.net_in,
            "net_out": r.net_out,
        }
        for r in reversed(rows)
    ]


def _query_rankings(db: Session, limit: int = 8) -> list[dict]:
    from app.analyzers.query_analyzer import most_expensive
    rankings = most_expensive(db, limit)
    for r in rankings:
        r["last_seen"] = _iso(r.get("last_seen"))
    return rankings


def _active_alerts(db: Session) -> int:
    return db.scalar(select(func.count(Alert.id)).where(Alert.active == True)) or 0  # noqa: E712


def _snapshot(db: Session) -> dict:
    return {
        "server": _server(db),
        "latest": _latest_system(db),
        "series": _recent_system(db, 120),
        "expensive": _query_rankings(db),
        "alerts_active": _active_alerts(db),
    }


# --- WebSocket live updates --------------------------------------------------

@router.websocket("/ws")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    factory = get_session_factory()
    try:
        while True:
            db = factory()
            try:
                payload = _snapshot(db)
            finally:
                db.close()
            await websocket.send_json(payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# --- JSON API ----------------------------------------------------------------

@router.get("/api/overview")
def api_overview(_: None = Depends(require_key), db: Session = Depends(get_db)):
    return _snapshot(db)


@router.get("/api/queries")
def api_queries(limit: int = Query(20), _: None = Depends(require_key),
                db: Session = Depends(get_db)):
    from app.analyzers.query_analyzer import most_expensive, worst_latency
    return {"most_expensive": most_expensive(db, limit),
            "worst_latency": worst_latency(db, limit)}


@router.get("/api/server-health")
def api_health(_: None = Depends(require_key), db: Session = Depends(get_db)):
    return {"system_metrics": _recent_system(db)}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/api/alerts")
def api_alerts(from_: str = Query(None, alias="from"),
               to_: str = Query(None, alias="to"),
               _: None = Depends(require_key), db: Session = Depends(get_db)):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(500)
    if from_ := _parse_dt(from_):
        stmt = stmt.where(Alert.created_at >= from_)
    if to := _parse_dt(to_):
        stmt = stmt.where(Alert.created_at <= to)
    rows = db.scalars(stmt).all()
    return [
        {"id": a.id, "type": a.type, "severity": a.severity, "message": a.message,
         "value": a.value, "threshold": a.threshold, "active": a.active,
         "created_at": a.created_at}
        for a in rows
    ]


@router.get("/api/alerts/summary")
def api_alerts_summary(from_: str = Query(None, alias="from"),
                       to_: str = Query(None, alias="to"),
                       _: None = Depends(require_key), db: Session = Depends(get_db)):
    stmt = (select(func.date(Alert.created_at).label("day"), Alert.severity,
                   func.count(Alert.id).label("n"))
            .group_by("day", Alert.severity).order_by("day"))
    if from_ := _parse_dt(from_):
        stmt = stmt.where(Alert.created_at >= from_)
    if to := _parse_dt(to_):
        stmt = stmt.where(Alert.created_at <= to)
    return [{"day": r.day, "severity": r.severity, "count": r.n} for r in db.execute(stmt).all()]


@router.get("/api/recommendations")
def api_recommendations(_: None = Depends(require_key), db: Session = Depends(get_db)):
    rows = db.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()).limit(100)).all()
    return [{"type": r.type, "title": r.title, "detail": r.detail,
             "sql": r.sql, "severity": r.severity, "created_at": r.created_at} for r in rows]


@router.get("/api/reports")
def api_reports(_: None = Depends(require_key), db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).order_by(Report.created_at.desc()).limit(50)).all()
    return [{"filename": r.filename, "health_score": r.health_score,
             "created_at": r.created_at} for r in rows]


# --- Dashboard pages ---------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "main.html", {"snapshot": _snapshot(db)})


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    return templates.TemplateResponse(request, "logs.html", {})
