from app.analyzers.memory_analyzer import estimate, per_connection_memory
from app.models import MySqlServer


def test_per_connection_memory_positive():
    assert per_connection_memory() > 0


def test_estimate_risk_low_when_buffer_small():
    server = MySqlServer(max_connections=100, innodb_buffer_pool_size=1 * 1024 ** 3)
    result = estimate(server, ram_bytes=32 * 1024 ** 3)
    assert result["risk"] == "low"
    assert result["ram_gb"] == 32
    assert result["estimated_bytes"] > 0


def test_estimate_risk_high_when_buffer_exceeds_ram():
    server = MySqlServer(max_connections=400, innodb_buffer_pool_size=24 * 1024 ** 3)
    result = estimate(server, ram_bytes=16 * 1024 ** 3)
    assert result["risk"] == "high"


def test_estimate_uses_server_max_connections_when_not_given():
    server = MySqlServer(max_connections=200, innodb_buffer_pool_size=4 * 1024 ** 3)
    result = estimate(server, ram_bytes=32 * 1024 ** 3, max_connections=None)
    assert result["max_connections"] == 200
