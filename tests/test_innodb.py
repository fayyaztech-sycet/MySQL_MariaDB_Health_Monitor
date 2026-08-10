from app.collectors.innodb import parse_status

SAMPLE = """
BUFFER POOL AND MEMORY
Buffer pool size   8192
Modified db pages 123
History list length 45
Pending writes: 2
Buffer pool hit rate 998 / 1000, young-making rate 0 / 1000
------------------------
LATEST DETECTED DEADLOCK
------------------------
"""


def test_parse_status_fields():
    out = parse_status(SAMPLE)
    assert out["buffer_hit_ratio"] == 99.8
    assert out["dirty_pages"] == 123
    assert out["history_list_len"] == 45
    assert out["pending_io"] == 2
    assert out["deadlocks"] == 1


def test_parse_status_no_deadlock():
    text = SAMPLE.replace("LATEST DETECTED DEADLOCK", "")
    assert parse_status(text)["deadlocks"] == 0


def test_parse_status_empty():
    out = parse_status("")
    assert out == {
        "buffer_hit_ratio": 0.0,
        "deadlocks": 0,
        "dirty_pages": 0,
        "pending_io": 0,
        "history_list_len": 0,
    }
