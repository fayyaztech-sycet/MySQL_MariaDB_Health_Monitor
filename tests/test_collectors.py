from app.collectors import mysql_status, slow_queries, innodb, system_metrics
from app.models import MySqlServer, QueryStats, SystemMetrics
from sqlalchemy import select

from conftest import FakeConn


def _status_routes():
    """Custom router that distinguishes the two SHOW VARIABLES LIKE params."""
    def router(sql, params):
        s = sql.lower()
        if "select version()" in s:
            return [{"v": "8.0.36"}]
        if "show global status" in s:
            return [{"Variable_name": "Threads_connected", "Value": "12"},
                    {"Variable_name": "Uptime", "Value": "3600"}]
        if "show global variables like" in s:
            name = params[0] if params else ""
            return [{"Value": {"max_connections": "151",
                               "innodb_buffer_pool_size": str(1024 ** 3)}.get(name, "")}]
        if "information_schema.tables" in s:
            return [{"sz": str(5 * 1024 ** 3)}]
        return []
    return router


def test_mysql_status_upserts_server(session):
    conn = FakeConn(_status_routes())

    written = mysql_status.collect(session, conn)
    assert written == 1
    server = session.scalar(select(MySqlServer).limit(1))
    assert server.version == "8.0.36"
    assert server.threads_connected == 12
    assert server.max_connections == 151
    assert server.database_size_bytes == 5 * 1024 ** 3


def test_mysql_status_idempotent_no_duplicate(session):
    conn = FakeConn(_status_routes())
    mysql_status.collect(session, conn)
    mysql_status.collect(session, conn)
    assert len(session.scalars(select(MySqlServer)).all()) == 1


def test_slow_queries_delta(session):
    import app.collectors.slow_queries as sq
    sq._baseline = {}

    # hostname must match settings default (localhost) so collect finds the server
    srv = MySqlServer(hostname="localhost", port=3306)
    session.add(srv)
    session.flush()

    def digest_rows(count, timer):
        return [{"SCHEMA_NAME": "erp", "DIGEST": None, "DIGEST_TEXT": "SELECT * FROM students WHERE id = ?",
                 "COUNT_STAR": count, "SUM_TIMER_WAIT": timer,
                 "AVG_TIMER_WAIT": 0, "MAX_TIMER_WAIT": 0,
                 "SUM_ROWS_EXAMINED": 1000, "SUM_ROWS_SENT": 10}]

    # First run: establish baseline -> 0 rows written
    conn1 = FakeConn({"performance_schema.events_statements_summary_by_digest": digest_rows(100, 5000)})
    assert sq.collect(session, conn1) == 0

    # Second run: delta of +50 calls, +2500 timer picoseconds -> 0.0000025 ms
    conn2 = FakeConn({"performance_schema.events_statements_summary_by_digest": digest_rows(150, 7500)})
    written = sq.collect(session, conn2)
    assert written == 1

    stats = session.scalar(select(QueryStats).limit(1))
    assert stats.calls == 50
    assert stats.total_ms == 2500 / 1e9


def test_innodb_collect(session):
    text = "BUFFER POOL AND MEMORY\nModified db pages 7\nHistory list length 3\nPending writes: 1\nBuffer pool hit rate 990 / 1000"
    conn = FakeConn({"show engine innodb status": [{"Status": text}]})
    assert innodb.collect(session, conn) == 1


def test_system_metrics_stores_load_averages(session):
    """Load 1/5/15 min averages are persisted by the system collector."""
    assert system_metrics.collect(session, conn=None) == 1
    row = session.scalar(select(SystemMetrics).limit(1))
    assert row is not None
    # Values come from psutil.getloadavg(); all three must be filled.
    for attr in ("load_avg", "load_avg_5", "load_avg_15"):
        assert getattr(row, attr) is not None
    # The 15-min average is the smoothest and should be >= 0.
    assert row.load_avg_15 >= 0.0
