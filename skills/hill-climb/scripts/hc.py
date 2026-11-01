#!/usr/bin/env python3
"""hc.py: small, dependency-free helpers for a hill-climb run.

  hc.py setup --cmd CMD --direction min|max [opts]   init, plus the run's frozen config for `round`
  hc.py baseline                         gates and score on the untouched tree, logged as round 0
  hc.py round "CHANGE"                   one whole round: commit, gates, score, keep or revert, log, next step
  hc.py init [DIR]                       write HILLCLIMB.md and results.tsv into DIR/.hillclimb
  hc.py measure [opts] -- CMD ...        run CMD N times, print the metric's median and spread as JSON
  hc.py compare BEST.json CAND.json      noise-aware verdict: WIN, LOSS or NOISE
  hc.py flip --judges N --best D --cand D --out D   blind A/B per judge, neutral file copies, flip.json
  hc.py log FILE key=value ...           append one row to results.tsv
  hc.py status FILE [--patience N] [--budget N]   rounds, best vs baseline, whether a stop rule fired

Standard library only. Python 3.8+.
"""
import argparse
import json
import math
import os
import re
import secrets
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime

COLUMNS = ["round", "time", "commit", "change", "score", "gates", "verdict", "notes"]
KEEP_VERDICTS = {"baseline", "keep", "win"}
HERE = os.path.dirname(os.path.abspath(__file__))


def cmd_init(a):
    d = os.path.join(a.dir, ".hillclimb")
    os.makedirs(os.path.join(d, "rounds"), exist_ok=True)
    tpl = os.path.join(HERE, "..", "references", "setup-template.md")
    setup = os.path.join(d, "HILLCLIMB.md")
    if not os.path.exists(setup):
        text = open(tpl).read().replace("<date>", datetime.now().strftime("%Y-%m-%d"))
        head = subprocess.run(["git", "-C", a.dir, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        sha = subprocess.run(["git", "-C", a.dir, "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        if head.returncode == 0 and sha.returncode == 0:
            text = text.replace("<branch>@<sha>", f"{head.stdout.strip()}@{sha.stdout.strip()}")
        with open(setup, "w") as f:
            f.write(text)
    tsv = os.path.join(d, "results.tsv")
    if not os.path.exists(tsv):
        with open(tsv, "w") as f:
            f.write("\t".join(COLUMNS) + "\n")
    # Keep the run's files out of the tracked tree without editing .gitignore.
    git_dir = subprocess.run(["git", "-C", a.dir, "rev-parse", "--git-dir"],
                             capture_output=True, text=True)
    if git_dir.returncode == 0:
        exclude = os.path.join(a.dir, git_dir.stdout.strip(), "info", "exclude")
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        existing = open(exclude).read() if os.path.exists(exclude) else ""
        if ".hillclimb/" not in existing.split():
            with open(exclude, "a") as f:
                f.write("\n.hillclimb/\n")
    print(json.dumps({"setup": setup, "log": tsv, "git": git_dir.returncode == 0}))


def _one_run(cmd, regex, timeout, expect=()):
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    wall = time.perf_counter() - t0
    if p.returncode != 0:
        return None, f"exit {p.returncode}: {(p.stderr or p.stdout).strip()[-300:]}"
    output = p.stdout + "\n" + p.stderr
    for pattern in expect:
        if not re.search(pattern, output, re.MULTILINE):
            return None, f"expected output missing: {pattern}"
    if not regex:
        return wall, None
    m = re.findall(regex, output, re.MULTILINE)
    if not m:
        return None, "metric not found in output"
    last = m[-1]
    return float(last[0] if isinstance(last, tuple) else last), None


def cmd_measure(a):
    parts = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    cmd = " ".join(parts).strip()
    if not cmd:
        sys.exit("measure: give the command after --")
    expect = list(a.expect) + [r"^" + re.escape(line) + r"$" for line in a.expect_line]
    a.expect = expect
    for _ in range(a.warmup):
        _one_run(cmd, a.regex, a.timeout, a.expect)
    samples, errors = [], []
    for _ in range(a.runs):
        v, err = _one_run(cmd, a.regex, a.timeout, a.expect)
        if err:
            errors.append(err)
            if a.fail_fast:
                break
        else:
            samples.append(v)
    out = {"cmd": cmd, "metric": a.regex or "wall_seconds", "expect": expect,
           "samples": samples, "errors": errors}
    if samples:
        med = statistics.median(samples)
        out["median"] = med
        out["mad"] = statistics.median([abs(x - med) for x in samples])
    out["ok"] = bool(samples) and not errors
    text = json.dumps(out, indent=1)
    if a.out:
        with open(a.out, "w") as f:
            f.write(text + "\n")
    print(text)


def cmd_compare(a):
    best, cand = (json.load(open(p)) for p in (a.best, a.cand))
    if not cand.get("ok"):
        print(json.dumps({"verdict": "LOSS", "reason": "candidate run failed", "errors": cand.get("errors")}))
        return
    b, c = best["median"], cand["median"]
    gain = (b - c) if a.direction == "min" else (c - b)
    rel = gain / abs(b) if b else math.copysign(math.inf, gain) if gain else 0.0
    # Noise band: twice the pooled MAD, relative to the incumbent.
    noise = 2 * (best.get("mad", 0) + cand.get("mad", 0)) / abs(b) if b else 0.0
    bar = max(a.min_delta, noise)
    # A tie is never a win, even with --min-delta 0 on a deterministic count.
    if rel > 0 and rel >= bar:
        verdict = "WIN"
    elif rel < 0 and rel <= -bar:
        verdict = "LOSS"
    else:
        verdict = "NOISE"
    print(json.dumps({"verdict": verdict, "best": b, "candidate": c, "gain_rel": round(rel, 4),
                      "bar_rel": round(bar, 4), "noise_rel": round(noise, 4),
                      "min_delta": a.min_delta, "direction": a.direction}))


def cmd_flip(a):
    rows = []
    for j in range(1, a.judges + 1):
        cand_is_a = secrets.randbits(1) == 1
        row = {"judge": j, "A": "candidate" if cand_is_a else "best",
               "B": "best" if cand_is_a else "candidate"}
        if a.out:
            # File paths unblind a judge as surely as labels do (r00 vs r07), so each judge
            # gets copies under neutral names: OUT/judge-N/A/<file>, OUT/judge-N/B/<file>.
            src = {"candidate": a.cand, "best": a.best}
            for side in ("A", "B"):
                dst = os.path.join(a.out, f"judge-{j}", side)
                os.makedirs(dst, exist_ok=True)
                for name in sorted(os.listdir(src[row[side]])):
                    if any(name.endswith(ext) for ext in a.ext.split(",")):
                        shutil.copyfile(os.path.join(src[row[side]], name), os.path.join(dst, name))
            row["dir"] = os.path.join(a.out, f"judge-{j}")
        rows.append(row)
    text = json.dumps(rows)
    if a.out:
        # The mapping stays outside the judge folders; record it before any judge runs.
        with open(os.path.join(a.out, "flip.json"), "w") as f:
            f.write(text + "\n")
    print(text)


def _read(path):
    with open(path) as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def cmd_log(a):
    row = {k: "" for k in COLUMNS}
    row["time"] = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    for kv in a.fields:
        k, _, v = kv.partition("=")
        if k not in row:
            sys.exit(f"log: unknown column {k!r}; columns are {', '.join(COLUMNS)}")
        row[k] = v.replace("\t", " ").replace("\n", " ")
    if not row["commit"]:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
        row["commit"] = r.stdout.strip() if r.returncode == 0 else "-"
    if not row["round"]:
        row["round"] = str(len(_read(a.file)))
    with open(a.file, "a") as f:
        f.write("\t".join(row[k] for k in COLUMNS) + "\n")
    if not getattr(a, "quiet", False):
        print(json.dumps(row))


def cmd_status(a):
    rows = _read(a.file)
    if not rows:
        sys.exit("status: no rounds logged yet")
    kept = [r for r in rows if r["verdict"].lower() in KEEP_VERDICTS]
    since_win = 0
    for r in reversed(rows):
        if r["verdict"].lower() in KEEP_VERDICTS:
            break
        since_win += 1
    rounds = len(rows) - 1  # row 0 is the baseline
    stop = []
    if a.budget and rounds >= a.budget:
        stop.append(f"budget of {a.budget} rounds used")
    if a.patience and since_win >= a.patience:
        stop.append(f"{since_win} rounds without a win (patience {a.patience})")
    print(json.dumps({"rounds": rounds, "wins": len(kept) - 1, "rounds_since_win": since_win,
                      "baseline": rows[0]["score"], "best": kept[-1]["score"] if kept else None,
                      "best_round": kept[-1]["round"] if kept else None,
                      "stop": stop or None}, indent=1))


CONFIG = os.path.join(".hillclimb", "config.json")
BEST = os.path.join(".hillclimb", "rounds", "best.json")
LOG = os.path.join(".hillclimb", "results.tsv")


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _measure_cfg(cfg, out):
    ns = argparse.Namespace(cmd=["--", cfg["cmd"]], regex=cfg.get("regex"), runs=cfg["runs"], warmup=cfg["warmup"],
                            expect=cfg.get("expect", []), expect_line=cfg.get("expect_line", []),
                            timeout=cfg["timeout"], fail_fast=True, out=out)
    with open(os.devnull, "w") as devnull:
        stdout, sys.stdout = sys.stdout, devnull
        try:
            cmd_measure(ns)
        finally:
            sys.stdout = stdout
    return json.load(open(out))


def _gates(cfg, base_commit):
    if cfg.get("frozen") and base_commit:
        changed = _git("diff", "--name-only", base_commit, "HEAD", "--", *cfg["frozen"]).stdout.split()
        if changed:
            return f"frozen file changed: {', '.join(changed)}"
    for g in cfg.get("gates", []):
        try:
            r = subprocess.run(g, shell=True, capture_output=True, text=True, timeout=cfg["timeout"])
        except subprocess.TimeoutExpired:
            return f"gate timed out: {g}"
        if r.returncode != 0:
            return f"gate failed: {g}: {(r.stdout + r.stderr).strip()[-300:]}"
    return None


def cmd_setup(a):
    cmd_init(argparse.Namespace(dir="."))
    cfg = {"cmd": a.cmd, "regex": a.regex, "direction": a.direction, "min_delta": a.min_delta, "runs": a.runs,
           "warmup": a.warmup, "expect": a.expect, "expect_line": a.expect_line, "gates": a.gate,
           "frozen": a.frozen, "budget": a.budget, "patience": a.patience, "timeout": a.timeout}
    if os.path.exists(CONFIG) and not a.force:
        sys.exit("setup: .hillclimb/config.json exists; the score never changes mid-run (use --force to restart "
                 "the run at a new round 0, and note why under Restarts in HILLCLIMB.md)")
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=1)
    print(json.dumps(cfg, indent=1))
    print("NEXT: fill in .hillclimb/HILLCLIMB.md, commit any pending work, then run: hc.py baseline")


def _next(cfg, rows_since_win, rounds, wins):
    stop = []
    if cfg["budget"] and rounds >= cfg["budget"]:
        stop.append(f"budget of {cfg['budget']} rounds used")
    if cfg["patience"] and rows_since_win >= cfg["patience"]:
        stop.append(f"{rows_since_win} rounds in a row without a win (patience {cfg['patience']})")
    if stop:
        return "STOP: " + "; ".join(stop) + ". Confirm the best against the baseline, then write the report."
    msg = (f"NEXT: round {rounds + 1} of {cfg['budget'] or 'unlimited'}. Make ONE change (not to frozen files) "
           f"and run: hc.py round \"<what you changed>\". The run is not over until this prints STOP; "
           f"a big win is not a stop rule.")
    half = math.ceil(cfg["patience"] / 2) if cfg["patience"] and cfg["patience"] > 2 else 0
    if half and rows_since_win == half:
        msg += " Big move due: try a different approach altogether, not a tweak (notes=big-move)."
    return msg


def cmd_baseline(a):
    cfg = json.load(open(CONFIG))
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit("baseline: commit or stash tracked changes first")
    head = _git("rev-parse", "--short", "HEAD").stdout.strip()
    err = _gates(cfg, None)
    if err:
        sys.exit(f"baseline: {err}. The gates must pass on the untouched version; fix the setup, not the gate.")
    res = _measure_cfg(cfg, os.path.join(".hillclimb", "rounds", "r00.json"))
    if not res["ok"]:
        sys.exit(f"baseline: measurement failed: {res['errors'][:1]}")
    res["commit"], res["base_commit"] = head, head
    with open(BEST, "w") as f:
        json.dump(res, f, indent=1)
    cmd_log(argparse.Namespace(file=LOG, quiet=True, fields=["round=0", "change=baseline", f"score={res['median']:.6g}",
                                                 "gates=pass", "verdict=baseline", f"notes=mad {res['mad']:.3g}"]))
    print(_next(cfg, 0, 0, 0))


def cmd_round(a):
    cfg = json.load(open(CONFIG))
    best = json.load(open(BEST))
    rows = _read(LOG)
    n = len(rows)
    _git("add", "-A")
    if _git("diff", "--cached", "--quiet").returncode != 0:
        _git("commit", "-q", "-m", f"r{n:02d}: {a.change}")
    head = _git("rev-parse", "--short", "HEAD").stdout.strip()
    if _git("rev-parse", "HEAD").stdout.strip() == _git("rev-parse", best["commit"]).stdout.strip():
        sys.exit("round: nothing changed since the best; make one change first")
    verdict, score, notes, gates = None, "", "", "pass"
    if a.verdict:
        err = _gates(cfg, best["base_commit"])
        if err:
            verdict, gates, notes = "LOSS", "fail", err
        else:
            verdict, score, notes = a.verdict.upper(), a.score or "", a.notes or ""
    else:
        err = _gates(cfg, best["base_commit"])
        if err:
            verdict, gates, notes = "LOSS", "fail", err
        else:
            out = os.path.join(".hillclimb", "rounds", f"r{n:02d}.json")
            cand = _measure_cfg(cfg, out)
            if not cand["ok"]:
                verdict, gates, notes = "LOSS", "fail", f"measurement failed: {cand['errors'][:1]}"
            else:
                cmp_ns = argparse.Namespace(best=BEST, cand=out, direction=cfg["direction"], min_delta=cfg["min_delta"])
                buf = __import__("io").StringIO()
                stdout, sys.stdout = sys.stdout, buf
                try:
                    cmd_compare(cmp_ns)
                finally:
                    sys.stdout = stdout
                c = json.loads(buf.getvalue())
                verdict, score = c["verdict"], f"{cand['median']:.6g}"
                notes = f"gain {c['gain_rel']:+.1%}, bar {c['bar_rel']:.1%}"
                if verdict == "NOISE" and a.simpler:
                    verdict, notes = "KEEP", notes + ", simpler"
    if a.notes and not a.verdict:
        notes = f"{notes}, {a.notes}" if notes else a.notes
    keep = verdict in ("WIN", "KEEP")
    cmd_log(argparse.Namespace(file=LOG, quiet=True, fields=[f"round={n}", f"commit={head}", f"change={a.change}",
                                                 f"score={score}", f"gates={gates}",
                                                 f"verdict={'keep' if keep else 'revert'}",
                                                 f"notes={verdict}: {notes[:200]}"]))
    if keep:
        if not a.verdict:
            new = json.load(open(os.path.join(".hillclimb", "rounds", f"r{n:02d}.json")))
            new["commit"], new["base_commit"] = head, best["base_commit"]
            with open(BEST, "w") as f:
                json.dump(new, f, indent=1)
        else:
            best["commit"] = head
            with open(BEST, "w") as f:
                json.dump(best, f, indent=1)
    else:
        _git("reset", "-q", "--hard", best["commit"])
    rows = _read(LOG)
    since = 0
    for r in reversed(rows):
        if r["verdict"].lower() in KEEP_VERDICTS:
            break
        since += 1
    wins = sum(r["verdict"].lower() == "keep" for r in rows)
    print(f"{verdict}: {notes}" + (" -> kept" if keep else f" -> reverted to {best['commit']}"))
    print(_next(cfg, since, len(rows) - 1, wins))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="sub", required=True)

    s = sub.add_parser("setup")
    s.add_argument("--cmd", required=True, help="the scoring command, run from the repo root")
    s.add_argument("--regex", help="metric = group 1 of the last match; omit to score the command's wall time")
    s.add_argument("--direction", choices=["min", "max"], required=True)
    s.add_argument("--min-delta", type=float, default=0.02)
    s.add_argument("--runs", type=int, default=5)
    s.add_argument("--warmup", type=int, default=1)
    s.add_argument("--expect", action="append", default=[], metavar="REGEX")
    s.add_argument("--expect-line", action="append", default=[], metavar="TEXT")
    s.add_argument("--gate", action="append", default=[], metavar="CMD", help="must exit 0 (repeatable)")
    s.add_argument("--frozen", action="append", default=[], metavar="PATH", help="may not change (repeatable)")
    s.add_argument("--budget", type=int, default=20)
    s.add_argument("--patience", type=int, default=5)
    s.add_argument("--timeout", type=float, default=600)
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("baseline")
    s.set_defaults(fn=cmd_baseline)

    s = sub.add_parser("round")
    s.add_argument("change", help="the one change this round made, in a few words")
    s.add_argument("--verdict", choices=["WIN", "LOSS", "NOISE", "win", "loss", "noise"],
                   help="judge mode: the unblinded panel verdict, decided outside this script")
    s.add_argument("--score", help="judge mode: the vote, e.g. '3/3 cand'")
    s.add_argument("--simpler", action="store_true", help="the change deletes more than it adds: keep it at equal score")
    s.add_argument("--notes")
    s.set_defaults(fn=cmd_round)

    s = sub.add_parser("init")
    s.add_argument("dir", nargs="?", default=".")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("measure")
    s.add_argument("--runs", type=int, default=5)
    s.add_argument("--warmup", type=int, default=1)
    s.add_argument("--regex", help="metric = group 1 (or whole match) of the last match in stdout+stderr; "
                                   "omit to use the command's wall time in seconds")
    s.add_argument("--expect", action="append", default=[], metavar="REGEX",
                   help="output must match this (repeatable); a miss fails the run, like a gate")
    s.add_argument("--expect-line", action="append", default=[], metavar="TEXT",
                   help="output must contain this exact line, taken literally (repeatable)")
    s.add_argument("--timeout", type=float, default=600)
    s.add_argument("--fail-fast", action="store_true")
    s.add_argument("--out")
    s.add_argument("cmd", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_measure)

    s = sub.add_parser("compare")
    s.add_argument("best")
    s.add_argument("cand")
    s.add_argument("--direction", choices=["min", "max"], required=True)
    s.add_argument("--min-delta", type=float, default=0.01, help="smallest relative gain that counts (0.01 = 1%%)")
    s.set_defaults(fn=cmd_compare)

    s = sub.add_parser("flip")
    s.add_argument("--judges", type=int, default=1)
    s.add_argument("--best", help="folder with the best version's artifacts")
    s.add_argument("--cand", help="folder with the candidate's artifacts")
    s.add_argument("--out", help="write blinded copies per judge here, plus flip.json")
    s.add_argument("--ext", default=".png,.jpg,.jpeg,.webp,.txt,.md,.html,.svg",
                   help="comma-separated file endings to copy")
    s.set_defaults(fn=cmd_flip)

    s = sub.add_parser("log")
    s.add_argument("file")
    s.add_argument("fields", nargs="+")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("status")
    s.add_argument("file")
    s.add_argument("--patience", type=int, default=0)
    s.add_argument("--budget", type=int, default=0)
    s.set_defaults(fn=cmd_status)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
