"""OS health collector using psutil. Does not require a MySQL connection."""
from __future__ import annotations

import psutil

from app.models import SystemMetrics


def _disk_io():
    try:
        return psutil.disk_io_counters()
    except Exception:
        return None


def _net_io():
    try:
        return psutil.net_io_counters()
    except Exception:
        return None


def collect(session, conn=None) -> int:
    """Sample CPU/RAM/disk/network and persist a SystemMetrics row.

    conn is accepted for interface uniformity; it is unused here.
    """
    cpu = psutil.cpu_percent(interval=None)
    _loads = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0)
    load1, load5, load15 = (_loads + (0.0, 0.0, 0.0))[:3]
    freq = None
    try:
        freq = psutil.cpu_freq().current if psutil.cpu_freq() else None
    except Exception:
        freq = None

    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    du = psutil.disk_usage("/")
    dio = _disk_io()
    nio = _net_io()

    row = SystemMetrics(
        cpu=cpu,
        load_avg=round(load1, 3),
        load_avg_5=round(load5, 3),
        load_avg_15=round(load15, 3),
        cpu_freq=freq,
        mem_total=vm.total,
        mem_used=vm.used,
        mem_avail=vm.available,
        swap_used=swap.used,
        swap_total=swap.total,
        disk_used=du.used,
        disk_total=du.total,
        disk_read=dio.read_bytes if dio else 0,
        disk_write=dio.write_bytes if dio else 0,
        net_in=nio.bytes_recv if nio else 0,
        net_out=nio.bytes_sent if nio else 0,
    )
    session.add(row)
    session.flush()
    return 1
