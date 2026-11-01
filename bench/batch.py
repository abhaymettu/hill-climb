"""Run every (task, arm, seed) cell that has no result yet, a few at a time, in a shuffled order.

    python bench/batch.py --seeds 1-6 --arms plain,loop,hillclimb --tasks logstats,tinyclf,slowsuite --jobs 3
"""
import argparse
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BENCH = Path(__file__).resolve().parent


def seeds(spec):
    lo, _, hi = spec.partition("-")
    return range(int(lo), int(hi or lo) + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="logstats,tinyclf,slowsuite")
    ap.add_argument("--arms", default="plain,loop,hillclimb")
    ap.add_argument("--seeds", default="1-6")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--skill-dir", default=None)
    a = ap.parse_args()
    cells = [(t, arm, s) for t in a.tasks.split(",") for arm in a.arms.split(",") for s in seeds(a.seeds)
             if not (BENCH / "runs" / f"{t}-{arm}-s{s}" / "meta.json").exists()]
    random.Random(0).shuffle(cells)
    print(f"{len(cells)} runs to do", flush=True)

    def one(cell):
        t, arm, s = cell
        cmd = [sys.executable, str(BENCH / "run.py"), "--task", t, "--arm", arm, "--seed", str(s), "--model", a.model]
        if a.skill_dir:
            cmd += ["--skill-dir", a.skill_dir]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr[-400:], flush=True)

    with ThreadPoolExecutor(a.jobs) as pool:
        list(pool.map(one, cells))


if __name__ == "__main__":
    main()
