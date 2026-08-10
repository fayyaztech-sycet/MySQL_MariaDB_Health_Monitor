"""Report generation registration. Importing this package wires the daily
report job into the scheduler registry."""
from app.scheduler.jobs import register

from .html_report import generate


def collect(session, conn) -> int:
    return 1 if generate(session) else 0


register("report", collect)
