"""Standalone scheduler worker entrypoint (optional).

Run the collectors/analyzers/reports in this process without serving HTTP:
    python run_worker.py

NOTE: Do NOT run this alongside the API on the same SQLite file for the same
monitored server — both would collect the same metrics. Use either the API
(which embeds the scheduler) OR a dedicated worker, not both.
"""
from __future__ import annotations

import logging
import signal
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    from app.db import init_db
    init_db()

    from app import collectors, analyzers, reports  # noqa: F401  (register)
    from app.scheduler.jobs import build_scheduler

    scheduler = build_scheduler()
    if not scheduler.get_jobs():
        logger.warning("no jobs registered; nothing to run")
        return
    scheduler.start()
    logger.info("worker started with %d jobs", len(scheduler.get_jobs()))

    stop = False

    def _handle(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)
    while not stop:
        try:
            sys.stdin.read(1)
        except KeyboardInterrupt:
            break
    scheduler.shutdown(wait=False)
    logger.info("worker stopped")


if __name__ == "__main__":
    main()
