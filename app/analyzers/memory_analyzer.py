"""MySQL memory requirement estimation (README section 6).

estimated = innodb_buffer_pool
          + (max_connections * per_connection_memory)
          + temporary_buffers

Compared against total RAM to produce a risk level. Inputs come from the
persisted mysql_servers row plus defaults from settings.
"""
from __future__ import annotations

import psutil

from app.models import MySqlServer


def per_connection_memory(sort_buffer=262144, join_buffer=262144,
                          read_buffer=131072, read_rnd_buffer=262144,
                          thread_stack=262144, net_buffer=16384,
                          tmp_table=16777216, max_heap=16777216) -> int:
    """Heuristic per-connection memory in bytes (MySQLTuner-style defaults)."""
    return (
        sort_buffer + join_buffer + read_buffer + read_rnd_buffer
        + thread_stack + net_buffer
        + min(tmp_table, max_heap)
    )


def estimate(server: MySqlServer, ram_bytes: int | None = None,
             max_connections: int | None = None) -> dict:
    ram = ram_bytes or psutil.virtual_memory().total
    max_conn = max_connections or server.max_connections or 151
    buffer_pool = server.innodb_buffer_pool_size or 0

    per_conn = per_connection_memory()
    estimated = buffer_pool + (max_conn * per_conn)
    temp_buffers = max_conn * 262144  # rough temp/thread buffers allowance
    estimated += temp_buffers

    ratio = (estimated / ram) if ram else 0.0
    if ratio >= 1.0:
        risk = "high"
    elif ratio >= 0.7:
        risk = "medium"
    else:
        risk = "low"

    return {
        "ram_bytes": ram,
        "ram_gb": round(ram / (1024 ** 3), 2),
        "innodb_buffer_pool_bytes": buffer_pool,
        "max_connections": max_conn,
        "per_connection_bytes": per_conn,
        "estimated_bytes": estimated,
        "estimated_gb": round(estimated / (1024 ** 3), 2),
        "ratio": round(ratio, 3),
        "risk": risk,
    }
