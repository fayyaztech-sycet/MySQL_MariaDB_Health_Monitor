"""Collector registration. Importing this package wires collectors into the
scheduler registry (idempotent). MySQL-dependent collectors require a live
monitored server at runtime; the scheduler isolates failures per job.
"""
from app.scheduler.jobs import register

from . import system_metrics, mysql_status, processlist, slow_queries, innodb

register("system", system_metrics.collect)
register("mysql", mysql_status.collect)
register("processlist", processlist.collect)
register("slow_queries", slow_queries.collect)
register("innodb", innodb.collect)
