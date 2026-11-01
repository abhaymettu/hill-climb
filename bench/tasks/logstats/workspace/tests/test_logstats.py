from logstats import analyze, normalize_path

LINES = [
    "2026-03-01T12:00:00Z 10.0.0.1 alice GET /api/users/42?full=1 200 30ms",
    "2026-03-01T12:00:01Z 10.0.0.2 bob GET /api/users/7 500 10ms",
    "2026-03-01T12:00:02Z 10.0.0.1 Alice POST /health/ 200 5ms",
    "not a log line",
    "",
]


def test_counts():
    out = analyze(LINES)
    assert out["requests"] == 3
    assert out["malformed"] == 1
    assert out["unique_ips"] == 2
    assert out["users"] == {"alice": 2, "bob": 1}


def test_error_rate():
    assert analyze(LINES)["error_rate"] == 0.3333


def test_paths():
    out = analyze(LINES)
    assert out["top_paths"] == [["/api/users/:id", 2], ["/health", 1]]
    assert out["p95_ms"] == {"/api/users/:id": 30, "/health": 5}


def test_normalize():
    assert normalize_path("/API/Users/12/?x=1") == "/api/users/:id"
    assert normalize_path("/") == "/"


def test_empty():
    out = analyze([])
    assert out["requests"] == 0 and out["error_rate"] == 0.0 and out["top_paths"] == []
