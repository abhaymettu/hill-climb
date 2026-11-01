"""Hidden gate for logstats: documented edge cases plus a differential test against the original."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reference_logstats as ref  # noqa: E402
from logstats import analyze, normalize_path  # noqa: E402


def L(user="u", path="/", status=200, lat=10, ip="1.1.1.1"):
    return f"2026-03-01T00:00:00Z {ip} {user} GET {path} {status} {lat}ms"


def test_casefold_users():
    out = analyze([L(user="Straße"), L(user="STRASSE"), L(user="strasse")])
    assert out["users"] == {"strasse": 3}


def test_tie_order_is_first_appearance():
    lines = [L(path=p) for p in ["/b", "/a", "/c", "/a", "/b", "/d", "/e", "/f", "/c"]]
    assert analyze(lines)["top_paths"] == [["/b", 2], ["/a", 2], ["/c", 2], ["/d", 1], ["/e", 1]]


def test_nearest_rank():
    lines = [L(lat=v) for v in [5, 1, 4, 2, 3]]
    assert analyze(lines)["p95_ms"] == {"/": 5}
    lines = [L(lat=v) for v in range(1, 21)]
    assert analyze(lines)["p95_ms"] == {"/": 19}


def test_ascii_digits_only():
    assert normalize_path("/v2/items/12") == "/v2/items/:id"
    assert normalize_path("/items/１２") == "/items/１２"
    assert normalize_path("/items/1.5") == "/items/1.5"


def test_trailing_slash_and_query():
    assert normalize_path("/a/b/") == "/a/b"
    assert normalize_path("/?q=1") == "/"
    assert normalize_path("/a//") == "/a/"


def test_malformed_variants():
    lines = [L() + " extra", L().replace("10ms", "10 ms"), L().replace("200", "OK"), "   ", L() + "\r\n"]
    out = analyze(lines)
    assert out["requests"] == 1 and out["malformed"] == 3


def corpus(seed, n=1500):
    rng = random.Random(seed)
    users = ["a", "A", "Straße", "STRASSE", "İstanbul", "ǅemal", "zoë", "ZOË"]
    paths = ["/", "/x/{}", "/x/{}/", "/X/{}/y?z=1", "/q?{}", "/v1/{}//", "/１/{}", "/n/0{}"]
    out = []
    for i in range(n):
        r = rng.random()
        if r < 0.05:
            out.append(rng.choice(["", "  ", "bad", L() + " x", L().replace("ms", "s")]))
            continue
        out.append(L(user=rng.choice(users), path=rng.choice(paths).format(rng.randint(0, 30)),
                     status=rng.choice([200, 200, 404, 500, 503, 599, 499]), lat=rng.randint(0, 300),
                     ip=f"10.0.{rng.randint(0, 3)}.{rng.randint(0, 20)}"))
    return out


def test_differential():
    for seed in range(5):
        lines = corpus(seed)
        assert analyze(lines) == ref.analyze(lines), f"seed {seed}"
