"""Benchmark for logstats.analyze. Prints the best-of-3 wall time and a checksum of the output."""
import hashlib
import json
import random
import time

from logstats import analyze


def make_corpus(n=6000, seed=7):
    rng = random.Random(seed)
    users = ["alice", "Bob", "carol", "DAVE", "erin", "Straße", "STRASSE", "zoë", "mallory", "trent"]
    users += [f"user{i}" for i in range(120)]
    paths = ["/", "/api/users/{}", "/api/users/{}/posts/", "/api/orders/{}?expand=items", "/Search?q={}",
             "/static/app.js", "/api/v2/items/{}", "/health/", "/api/users/{}/Settings", "/docs/page-{}"]
    lines = []
    for i in range(n):
        r = rng.random()
        if r < 0.01:
            lines.append("garbage line " + str(i))
            continue
        if r < 0.015:
            lines.append("")
            continue
        p = rng.choice(paths).format(rng.randint(1, 400))
        status = rng.choice([200] * 18 + [201, 404, 500, 503])
        latency = int(rng.expovariate(1 / 40)) + 1
        line = "2026-03-01T12:{:02d}:{:02d}Z 10.0.{}.{} {} {} {} {} {}ms".format(
            i // 60 % 60, i % 60, rng.randint(0, 9), rng.randint(0, 255), rng.choice(users),
            rng.choice(["GET", "POST"]), p, status, latency)
        if r < 0.03:
            line = line.replace(" ", "\t ", 2) + "\r\n"
        if r < 0.035:
            line = line.replace("ms", " ms")
        lines.append(line)
    return lines


def main():
    lines = make_corpus()
    best = float("inf")
    out = None
    for _ in range(3):
        t0 = time.perf_counter()
        out = analyze(lines)
        best = min(best, time.perf_counter() - t0)
    digest = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()[:16]
    print(f"seconds={best:.4f}")
    print(f"checksum={digest}")


if __name__ == "__main__":
    main()
