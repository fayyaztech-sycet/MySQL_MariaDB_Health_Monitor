from app.alerts.alerting import evaluate
from app.models import Alert, SystemMetrics
from sqlalchemy import select


def _seed_high_cpu(session):
    session.add(SystemMetrics(
        cpu=98, mem_total=16 * 1024 ** 3, mem_avail=8 * 1024 ** 3,
        disk_used=50 * 1024 ** 3, disk_total=100 * 1024 ** 3,
    ))
    session.flush()


def test_cpu_high_fires_alert(session):
    _seed_high_cpu(session)
    fired = evaluate(session, None)
    assert fired >= 1
    types = {a.type for a in session.scalars(select(Alert)).all()}
    assert "cpu_high" in types


def test_alert_dedup_prevents_second_fire(session):
    _seed_high_cpu(session)
    evaluate(session, None)
    # Second evaluation should not create a duplicate active cpu_high alert.
    evaluate(session, None)
    cpu_alerts = session.scalars(
        select(Alert).where(Alert.type == "cpu_high", Alert.active == True)  # noqa: E712
    ).all()
    assert len(cpu_alerts) == 1


def test_no_alert_when_healthy(session):
    session.add(SystemMetrics(
        cpu=30, mem_total=16 * 1024 ** 3, mem_avail=12 * 1024 ** 3,
        disk_used=30 * 1024 ** 3, disk_total=100 * 1024 ** 3,
    ))
    session.flush()
    assert evaluate(session, None) == 0
