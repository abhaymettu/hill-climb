"""Simulated service. Shipped to the agent only as compiled bytecode (simsvc.pyc): a black box."""
import math
import os
import random

RANGES = {"workers": (1, 64), "batch_size": (1, 512), "cache_mb": (0, 4096), "compression": (0, 9),
          "prefetch": (0, 16), "pool_timeout_ms": (1, 1000)}
MEMORY_BUDGET_MB = 2048


def validate(cfg):
    for k, (lo, hi) in RANGES.items():
        v = cfg[k]
        if not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"{k}={v!r} outside {lo}..{hi}")
    if cfg["cache_mb"] + 48 * cfg["workers"] > MEMORY_BUDGET_MB:
        raise ValueError("memory budget exceeded: cache_mb + 48 * workers must be <= 2048")


def true_p95(cfg):
    w, b, c, z, p, t = (cfg[k] for k in ("workers", "batch_size", "cache_mb", "compression", "prefetch",
                                         "pool_timeout_ms"))
    compute = 400 / min(w, 12) + 2.5 * max(0, w - 12)
    batching = 30 * math.exp(-b / 32) + 0.08 * b
    cache = 120 / (1 + c / 256) + 0.004 * c
    codec = 60 / (1 + 0.35 * z) + 3.2 * z
    ahead = -8 * (1 - math.exp(-p / 3)) + 0.9 * p
    pool = 15 * math.exp(-t / 50) + 0.01 * t
    return compute + batching + cache + codec + ahead + pool


def measure(cfg):
    validate(cfg)
    rng = random.Random(os.urandom(8))
    return true_p95(cfg) * math.exp(rng.gauss(0, 0.08))
