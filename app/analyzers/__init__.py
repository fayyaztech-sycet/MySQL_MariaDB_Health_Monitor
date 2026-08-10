"""Analysis registration. Importing this package wires the scheduled analysis
job into the scheduler registry."""
from app.scheduler.jobs import register

from . import analyze_job

register("analyze", analyze_job.collect)
