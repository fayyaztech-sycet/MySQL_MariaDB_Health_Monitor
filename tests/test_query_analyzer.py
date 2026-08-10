from app.analyzers.query_analyzer import most_expensive, worst_latency
from app.models import QueryStats


def _seed(session, srv_id):
    rows = [
        ("SELECT a FROM t1", 100, 8000.0, 80.0),
        ("SELECT b FROM t2", 10, 7000.0, 700.0),
        ("SELECT c FROM t3", 50, 1000.0, 20.0),
    ]
    for text, calls, total, avg in rows:
        session.add(QueryStats(
            server_id=srv_id, query_text=text, calls=calls, total_ms=total,
            avg_ms=avg, rows_examined=1000, rows_sent=10,
        ))
    session.flush()


def test_most_expensive_orders_by_total_time(session):
    from app.models import MySqlServer
    srv = MySqlServer(hostname="h", port=3306)
    session.add(srv)
    session.flush()
    _seed(session, srv.id)

    top = most_expensive(session, limit=3)
    assert [t["query"] for t in top] == ["SELECT a FROM t1", "SELECT b FROM t2", "SELECT c FROM t3"]


def test_worst_latency_orders_by_avg_time(session):
    from app.models import MySqlServer
    srv = MySqlServer(hostname="h", port=3306)
    session.add(srv)
    session.flush()
    _seed(session, srv.id)

    top = worst_latency(session, limit=3)
    assert top[0]["query"] == "SELECT b FROM t2"
    assert top[0]["avg_ms"] == 700.0
