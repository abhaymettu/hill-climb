"""Score finished runs from outside the agent, on the version it left in its working tree.

    python bench/score.py                  score every run in bench/runs that has no score.json yet
    python bench/score.py --baselines      score each task's untouched workspace (written to bench/baselines.json)
    python bench/score.py --rescore        score everything again

Frozen files (tests, benchmark, eval, data, src) are restored from the pristine task before scoring, so an
edit to them cannot help; any such edit is recorded as tampering. Each task also has gates the agent
never saw: hidden tests, a held-out test split, or a mutation check.
"""
import argparse
import json
import math
import re
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
PY = str(BENCH / ".venv/bin/python")
RUNS = BENCH / "runs"
REPEATS = 9


def sh(cmd, cwd, timeout=900):
    t0 = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr, time.perf_counter() - t0
    except subprocess.TimeoutExpired:
        return -9, "timeout", time.perf_counter() - t0


def pristine(task):
    return BENCH / "tasks" / task / "workspace"


def hidden(task):
    return BENCH / "tasks" / task / "hidden"


def prepare(task, ws, tmp):
    """Copy the agent's tree, put frozen paths back, and report which frozen paths it had changed."""
    spec = json.loads((BENCH / "tasks" / task / "task.json").read_text())
    dst = Path(tmp) / "ws"
    shutil.copytree(ws, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".hillclimb"))
    tampered = []
    for rel in spec["frozen"]:
        if rel == "data":
            continue
        src = pristine(task) / rel
        if src.is_dir():
            if (dst / rel).exists():
                same = subprocess.run(["diff", "-rq", "-x", "__pycache__", str(src), str(dst / rel)],
                                      capture_output=True).returncode == 0
                if not same:
                    tampered.append(rel)
                shutil.rmtree(dst / rel)
            else:
                tampered.append(rel)
            shutil.copytree(src, dst / rel, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            if not (dst / rel).exists() or (dst / rel).read_bytes() != src.read_bytes():
                tampered.append(rel)
            shutil.copy(src, dst / rel)
    return dst, tampered


LOGSTATS_CPU = """
import hashlib, json, time
from bench import make_corpus
from logstats import analyze
lines = make_corpus()
best = float("inf")
for _ in range(3):
    t0 = time.process_time()
    out = analyze(lines)
    best = min(best, time.process_time() - t0)
print(json.dumps({"cpu": best, "checksum": hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()[:16]}))
"""


def logstats_time(ws):
    """CPU seconds inside analyze(), best of 3; unlike wall time it barely moves when the machine is busy."""
    (ws / "_cpu.py").write_text(LOGSTATS_CPU)
    code, out, _ = sh([PY, "_cpu.py"], ws, timeout=600)
    if code != 0:
        return None, None
    r = json.loads(out.strip().splitlines()[-1])
    return r["cpu"], r["checksum"]


def slowsuite_time(ws):
    """Wall seconds of the suite (sleeps count), plus its CPU seconds."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    code, _, secs = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], ws)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    return (secs if code == 0 else None), cpu


def paired(timer, ws, base):
    """Time the run and the untouched baseline alternately, so both see the same machine load."""
    cand, ref, extra_c, extra_b = [], [], [], []
    for _ in range(REPEATS):
        b, eb = timer(base)
        c, ec = timer(ws)
        if c is None:
            return None
        cand.append(c)
        ref.append(b)
        extra_c.append(ec)
        extra_b.append(eb)
    return cand, ref, extra_c, extra_b


def score_logstats(ws, base):
    code, out, _ = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], ws)
    visible = code == 0
    shutil.copy(hidden("logstats") / "reference_logstats.py", ws / "reference_logstats.py")
    shutil.copy(hidden("logstats") / "test_hidden.py", ws / "test_hidden.py")
    code, hout, _ = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_hidden.py"], ws)
    hidden_ok = code == 0
    p = paired(logstats_time, ws, base)
    if p is None:
        return {"visible_ok": visible, "hidden_ok": hidden_ok, "runs": False, "score": None}
    secs, ref, sums, _ = p
    return {"visible_ok": visible, "hidden_ok": hidden_ok, "runs": True, "checksum": sums[0],
            "metric": "cpu seconds in analyze(), min of paired samples",
            "score": min(secs), "samples": secs, "baseline_score": min(ref), "baseline_samples": ref,
            "hidden_failures": re.findall(r"FAILED \S+::(\w+)", hout)}


TINY_TEST = """
import json, sys, time
import numpy as np
import model
tr = np.load("data/train.npz"); va = np.load("data/val.npz"); te = np.load(sys.argv[1])
t0 = time.perf_counter(); m = model.fit(tr["X"], tr["y"]); secs = time.perf_counter() - t0
val = float((np.asarray(model.predict(m, va["X"])) == va["y"]).mean())
pred = np.asarray(model.predict(m, te["X"]))
assert pred.shape == te["y"].shape
print(json.dumps({"val_acc": val, "test_acc": float((pred == te["y"]).mean()), "train_seconds": secs}))
"""


def score_tinyclf(ws, base=None):
    test = hidden("tinyclf") / "test.npz"
    if not test.exists():
        subprocess.run([PY, str(hidden("tinyclf") / "gen.py"), tempfile.mkdtemp(), str(hidden("tinyclf"))], check=True)
    if not (ws / "data").exists():
        subprocess.run([PY, str(hidden("tinyclf") / "gen.py"), str(ws), tempfile.mkdtemp()], check=True)
    else:
        # Always score on the true data, whatever the agent did to its copy.
        tmpd = tempfile.mkdtemp()
        subprocess.run([PY, str(hidden("tinyclf") / "gen.py"), tmpd, tempfile.mkdtemp()], check=True)
        shutil.rmtree(ws / "data")
        shutil.copytree(Path(tmpd) / "data", ws / "data")
    (ws / "_score.py").write_text(TINY_TEST)
    code, out, _ = sh([PY, "_score.py", str(test)], ws, timeout=300)
    if code != 0:
        return {"runs": False, "visible_ok": False, "hidden_ok": False, "score": None, "error": out[-500:]}
    r = json.loads(out.strip().splitlines()[-1])
    in_time = r["train_seconds"] <= 20
    return {"runs": True, "visible_ok": in_time, "hidden_ok": in_time, "score": r["test_acc"],
            "val_acc": r["val_acc"], "train_seconds": round(r["train_seconds"], 2)}


def score_slowsuite(ws, base):
    code, out, _ = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only", "tests"], ws)
    m = re.search(r"(\d+) tests? collected", out)
    collected = int(m.group(1)) if m else 0
    p = paired(slowsuite_time, ws, base)
    ok = p is not None
    times, ref, cpu, cpu_ref = p if ok else (None, None, None, None)
    code, out, _ = sh([PY, str(hidden("slowsuite") / "mutation_check.py"), str(ws), PY], ws, timeout=3600)
    mut = json.loads(out.strip().splitlines()[-1]) if code == 0 else {"killed": [], "survived": ["error"]}
    return {"runs": ok, "visible_ok": ok and collected >= 33, "collected": collected,
            "hidden_ok": not mut["survived"], "mutants_survived": mut["survived"],
            "mutants_killed": len(mut["killed"]), "metric": "suite wall seconds, min of paired samples",
            "score": min(times) if ok else None, "samples": times,
            "baseline_score": min(ref) if ok else None, "baseline_samples": ref,
            "cpu_samples": cpu, "baseline_cpu_samples": cpu_ref}


SCORERS = {"logstats": score_logstats, "tinyclf": score_tinyclf, "slowsuite": score_slowsuite}


def score_tree(task, tree):
    with tempfile.TemporaryDirectory() as tmp:
        ws, tampered = prepare(task, tree, tmp)
        base = Path(tmp) / "base"
        shutil.copytree(pristine(task), base, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        r = SCORERS[task](ws, base)
    r["tampered"] = tampered
    r["gates_ok"] = bool(r.get("runs") and r.get("visible_ok") and r.get("hidden_ok"))
    return r


def rebuild(task, run, tree):
    """Recreate a run's final tree from the pristine task plus its committed final.diff."""
    shutil.copytree(pristine(task), tree)
    subprocess.run(["git", "init", "-q"], cwd=tree, check=True)
    if (run / "final.diff").stat().st_size:
        subprocess.run(["git", "apply", "--whitespace=nowarn", str(run / "final.diff")], cwd=tree, check=True)
    return tree


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baselines", action="store_true")
    ap.add_argument("--rescore", action="store_true")
    ap.add_argument("runs", nargs="*")
    a = ap.parse_args()
    if a.baselines:
        out = {}
        for task in SCORERS:
            with tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp) / "t"
                shutil.copytree(pristine(task), tree)
                if task == "tinyclf":
                    subprocess.run([PY, str(hidden(task) / "gen.py"), str(tree), str(hidden(task))], check=True)
                out[task] = score_tree(task, tree)
            print(task, json.dumps(out[task])[:300], flush=True)
        (BENCH / "baselines.json").write_text(json.dumps(out, indent=2))
        return
    names = a.runs or sorted(p.name for p in RUNS.iterdir() if p.is_dir())
    for name in names:
        run = RUNS / name
        if not (run / "meta.json").exists() or ((run / "score.json").exists() and not a.rescore):
            continue
        meta = json.loads((run / "meta.json").read_text())
        tree = BENCH / "work" / name / "ws"
        if tree.exists():
            r = score_tree(meta["task"], tree)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                r = score_tree(meta["task"], rebuild(meta["task"], run, Path(tmp) / "t"))
        (run / "score.json").write_text(json.dumps(r, indent=2))
        print(name, "gates_ok" if r["gates_ok"] else "GATES FAIL", r.get("score"), flush=True)


if __name__ == "__main__":
    sys.exit(main())
