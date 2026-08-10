"""FastAPI application factory + lifespan bootstrap.

The lifespan initializes the SQLite DB, wires up registered collectors, and
starts the APScheduler background jobs. Collectors/analyzers register
themselves by importing this app (registration is idempotent via module-level
imports in app.collectors / app.analyzers).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_scheduler = None


def register_collectors() -> None:
    """Import collector modules so they self-register with the scheduler."""
    from app import collectors  # noqa: F401
    from app import analyzers  # noqa: F401
    from app import alerts  # noqa: F401
    from app import reports  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import init_db
    init_db()

    register_collectors()

    global _scheduler
    from app.scheduler.jobs import build_scheduler
    _scheduler = build_scheduler()
    if _scheduler.get_jobs():
        _scheduler.start()
        logger.info("scheduler started with %d jobs", len(_scheduler.get_jobs()))
    else:
        logger.info("no collectors registered; scheduler not started")

    yield

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")


def create_app() -> FastAPI:
    from app.api.routes import router

    settings = get_settings()
    app = FastAPI(title="MySQL Profiler", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        max_age=7200,          # 2-hour session
        session_cookie="sm_session",
        https_only=False,      # allow http in dev
        same_site="lax",
    )
    app.include_router(router)
    return app


app = create_app()
