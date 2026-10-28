"""Benchmark: prints `seconds=<float>` for one pass over a fixed synthetic corpus. Frozen."""
import random, time
from textstats import top_tokens, duplicate_groups

rng = random.Random(7)
verbs = ["GET", "POST", "PUT", "DELETE"]
paths = ["/api/users", "/api/orders", "/health", "/api/items/search", "/login", "/logout"]
words = [f"w{i}" for i in range(400)]
lines = []
for _ in range(3000):
    lines.append(f"{rng.choice(verbs)} {rng.choice(paths)} {rng.randint(100, 599)} "
                 f"user {rng.randint(1, 50)} " + " ".join(rng.choice(words) for _ in range(rng.randint(0, 3))))
t0 = time.perf_counter()
top = top_tokens(lines, 20)
groups = duplicate_groups(lines)
dt = time.perf_counter() - t0
print(f"check top={top[0]} groups={len(groups)} largest={max(map(len, groups))}")
print(f"seconds={dt:.4f}")
