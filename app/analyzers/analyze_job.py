"""Scheduled analysis job: runs recommendation + alert evaluation."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def collect(session, conn) -> int:
    """Run all analysis steps. conn may be None for analysis that is pure-DB."""
    total = 0

    from app.alerts.alerting import evaluate
    from app.analyzers.recommendation_engine import run as run_recommendations

    try:
        total += run_recommendations(session, conn)
    except Exception:
        logger.exception("recommendation engine failed")

    try:
        total += evaluate(session, conn)
    except Exception:
        logger.exception("alert evaluation failed")

    session.flush()
    return total
