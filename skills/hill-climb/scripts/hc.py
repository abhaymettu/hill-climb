#!/usr/bin/env python3
"""hc.py: small, dependency-free helpers for a hill-climb run.

  hc.py setup --cmd CMD --direction min|max [opts]   init, plus the run's frozen config for `round`
  hc.py setup --judges N [--judge-cmd CMD] [opts]     the same for a judge run (blind pairwise panel); with
                                         --judge-cmd, round calls the judges and writes their replies itself
  hc.py baseline                         gates and score on the untouched tree, content locks, logged as round 0
  hc.py preflight broken|cheat|skip      prove the measure sees a broken version and catches a cheat, before round 1
  hc.py round "CHANGE" [--panel PATH]    one whole round: commit, locks, gates, score, keep or revert, log, next step
  hc.py tally DIR                        read the judges' saved replies in a blind folder, unblind, write panel.json
  hc.py holdout [--panel PATH]           score the best on the held-out set now, or record a judged holdout check
  hc.py init [DIR]                       write HILLCLIMB.md and results.tsv into DIR/.hillclimb
  hc.py measure [opts] -- CMD ...        run CMD N times, print the metric's median and spread as JSON
  hc.py compare BEST.json CAND.json      noise-aware verdict: WIN, LOSS or NOISE
  hc.py flip --judges N --best D --cand D --out D   blind A/B per judge, neutral file copies, flip.json
  hc.py log FILE key=value ...           append one row to results.tsv
  hc.py status FILE [--patience N] [--budget N]   rounds, best vs baseline, whether a stop rule fired

Exit codes: 0 ok; 1 error; 2 refused before anything was committed; 3 round refused after committing (a `refused`
row is logged and the tree is back at the best).

Standard library only. Python 3.8+.
"""
import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shlex
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

COLUMNS = ["round", "time", "commit", "change", "score", "gates", "verdict", "notes"]
KEEP_VERDICTS = {"baseline", "keep", "win"}
HERE = os.path.dirname(os.path.abspath(__file__))

HC = ".hillclimb"
ROUNDS = os.path.join(HC, "rounds")
CONFIG = os.path.join(HC, "config.json")
PROMPT = os.path.join(HC, "judge-prompt.md")
LOCKS = os.path.join(HC, "locks.json")
PREFLIGHT = os.path.join(HC, "preflight.json")
HOLDOUT = os.path.join(HC, "holdout.json")
BEST = os.path.join(ROUNDS, "best.json")
R00 = os.path.join(ROUNDS, "r00.json")
LOG = os.path.join(HC, "results.tsv")
HOLDOUT_DIR = os.path.join(ROUNDS, "holdout")
RECEIPT = "judges.json"

FORMAT_VERSION = 2
ALWAYS_LOCKED = (CONFIG, PROMPT)
SKIP_IN_LOCKS = {".git", "__pycache__", ".pytest_cache"}
FLIP_EXT = ".png,.jpg,.jpeg,.webp,.txt,.md,.html,.svg"
VERDICT_LINE = re.compile(r"^\s*\**\s*VERDICT\s*\**\s*:\s*\**\s*(A|B|TIE)\s*\**\s*$", re.IGNORECASE)

LEGACY_WARNING = ("hc.py: legacy run (set up before content locks and the holdout); using the old checks. "
                  "Restart with setup --force to get them.")
JUDGE_CMD_REFUSAL = ("{what}: this run's judges are called by hc.py (setup --judge-cmd), so a panel or verdict "
                     "made outside it is not accepted; {how}")
VERDICT_REFUSAL = ("round: --verdict is not accepted; save each judge's reply as rounds/rNN/blind/judge-J.txt, "
                   "run hc.py tally, then round --panel (a judge run is set up with setup --judges N)")
PREFLIGHT_REFUSAL = ("round: pre-flight not done; run hc.py preflight broken and hc.py preflight cheat "
                     "(see SKILL.md section 2) or hc.py preflight skip --why \"...\"")
BROKEN_FAIL = ("FAIL: the measure cannot tell a broken version from the baseline; fix the capture, the views or "
               "the prompt before round 1.")


class PanelError(Exception):
    pass


class Refused(Exception):
    """A round that was committed but must not be judged: logged as `refused`, tree reset, exit 3."""


def _refuse(code, msg):
    print(msg, file=sys.stderr)
    sys.exit(code)


def _load(path):
    with open(path) as f:
        return json.load(f)


def _save(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


def _rel(path):
    return os.path.normpath(os.path.relpath(os.path.abspath(path)))


def _pct(x):
    return "n/a" if x is None else f"{x:+.1%}"


class Run:
    """The run's config and the format it was set up with. A legacy run predates content locks, the panel tally,
    the pre-flight and the holdout, and keeps the old checks so a run started before them is never refused."""

    def __init__(self):
        self.cfg = _load(CONFIG)
        self.v2 = "version" in self.cfg
        self.judge = bool(self.cfg.get("judges"))
        self.holdout = self.cfg.get("holdout_cmd") if self.v2 else None
        self.judge_cmd = self.cfg.get("judge_cmd") if self.v2 else None
        if not self.v2:
            print(LEGACY_WARNING, file=sys.stderr)


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


def _se(m):
    """Standard error of a median from its MAD: 1.4826 * MAD estimates sigma, 1.2533 * sigma / sqrt(n) the SE."""
    n = len(m.get("samples", [])) or 1
    return 1.858 * m.get("mad", 0) / math.sqrt(n)


def runs_for_bar(m, bar):
    """Runs per measurement that bring the noise band down to `bar` (relative), given this spread."""
    rel = 1.858 * m.get("mad", 0) / abs(m["median"]) if m.get("median") else 0
    return max(3, math.ceil((2 * math.sqrt(2) * rel / bar) ** 2)) if bar > 0 else None


def _compare(best, cand, direction, min_delta):
    if not cand.get("ok"):
        return {"verdict": "LOSS", "reason": "candidate run failed", "errors": cand.get("errors")}
    b, c = best["median"], cand["median"]
    gain = (b - c) if direction == "min" else (c - b)
    rel = gain / abs(b) if b else math.copysign(math.inf, gain) if gain else 0.0
    # Noise band: two standard errors of the difference of medians, relative to the incumbent. More runs
    # shrink it, so a small real gain can always be resolved by measuring more.
    noise = 2 * math.hypot(_se(best), _se(cand)) / abs(b) if b else 0.0
    bar = max(min_delta, noise)
    # A tie is never a win, even with --min-delta 0 on a deterministic count.
    if rel > 0 and rel >= bar:
        verdict = "WIN"
    elif rel < 0 and rel <= -bar:
        verdict = "LOSS"
    else:
        verdict = "NOISE"
    return {"verdict": verdict, "best": b, "candidate": c, "gain_rel": round(rel, 4),
            "bar_rel": round(bar, 4), "noise_rel": round(noise, 4),
            "min_delta": min_delta, "direction": direction}


def cmd_compare(a):
    print(json.dumps(_compare(_load(a.best), _load(a.cand), a.direction, a.min_delta)))


def _flip(judges, best, cand, out, ext=FLIP_EXT):
    rows = []
    for j in range(1, judges + 1):
        cand_is_a = secrets.randbits(1) == 1
        row = {"judge": j, "A": "candidate" if cand_is_a else "best",
               "B": "best" if cand_is_a else "candidate"}
        if out:
            # File paths unblind a judge as surely as labels do (r00 vs r07), so each judge
            # gets copies under neutral names: OUT/judge-N/A/<file>, OUT/judge-N/B/<file>.
            src = {"candidate": cand, "best": best}
            for side in ("A", "B"):
                dst = os.path.join(out, f"judge-{j}", side)
                os.makedirs(dst, exist_ok=True)
                for name in sorted(os.listdir(src[row[side]])):
                    if any(name.endswith(e) for e in ext.split(",")):
                        shutil.copyfile(os.path.join(src[row[side]], name), os.path.join(dst, name))
            row["dir"] = os.path.join(out, f"judge-{j}")
        rows.append(row)
    if out:
        # The mapping stays outside the judge folders; record it before any judge runs.
        with open(os.path.join(out, "flip.json"), "w") as f:
            f.write(json.dumps(rows) + "\n")
    return rows


def cmd_flip(a):
    print(json.dumps(_flip(a.judges, a.best, a.cand, a.out, a.ext)))


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _reply_verdict(text):
    said = None
    for line in text.splitlines():
        m = VERDICT_LINE.match(line)
        if m:
            said = m.group(1).upper()
    return said


def _tally(d):
    flip_path = os.path.join(d, "flip.json")
    if not os.path.isfile(flip_path):
        raise PanelError(f"{flip_path} missing; run hc.py flip --out {d} first")
    try:
        rows = _load(flip_path)
    except ValueError:
        raise PanelError(f"{flip_path} is not valid JSON")
    receipt = _load(os.path.join(d, RECEIPT)) if os.path.isfile(os.path.join(d, RECEIPT)) else None
    saved = {r["judge"]: r["reply_sha256"] for r in receipt["judges"]} if receipt else {}
    votes = []
    for row in rows:
        j = row["judge"]
        reply = os.path.join(d, f"judge-{j}.txt")
        if not os.path.isfile(reply):
            raise PanelError(f"judge {j}: {reply} missing; save that judge's full reply there")
        with open(reply, encoding="utf-8-sig", errors="replace") as f:
            said = _reply_verdict(f.read())
        if not said:
            raise PanelError(f"judge {j}: no 'VERDICT: A|B|TIE' line in {reply}")
        sha = _sha_file(reply)
        if receipt and saved.get(j) != sha:
            raise PanelError(f"judge {j}: {reply} is not the reply hc.py saved from the judge command")
        votes.append({"judge": j, "reply": f"judge-{j}.txt", "reply_sha256": sha, "said": said,
                      "prefers": "tie" if said == "TIE" else row[said]})
    n = len(votes)
    count = {side: sum(v["prefers"] == side for v in votes) for side in ("candidate", "best", "tie")}
    verdict = "WIN" if count["candidate"] > n / 2 else "LOSS" if count["best"] > n / 2 else "NOISE"
    return {"dir": d, "judges": n, "votes": votes, "candidate": count["candidate"], "best": count["best"],
            "tie": count["tie"], "verdict": verdict, "score": f"{count['candidate']}/{n} cand",
            "flip_sha256": _sha_file(flip_path),
            "replies_written_by": receipt["caller"] if receipt else "the agent (hc.py cannot check who wrote them)"}


def cmd_tally(a):
    try:
        panel = _tally(a.dir)
    except PanelError as e:
        sys.exit(f"tally: {e}")
    _save(os.path.join(a.dir, "panel.json"), panel)
    print(json.dumps(panel, indent=1))


def _panel_fingerprint(panel):
    return (panel.get("verdict"), panel.get("flip_sha256"),
            [(v.get("judge"), v.get("reply_sha256")) for v in panel.get("votes", [])])


def _verify_panel(path, judges=None):
    """Recompute the tally from the replies beside panel.json; the saved file is never trusted on its own."""
    if not os.path.isfile(path):
        raise PanelError(f"{path} missing; run hc.py tally on its folder")
    try:
        saved = _load(path)
    except ValueError:
        raise PanelError(f"{path} is not valid JSON")
    fresh = _tally(os.path.dirname(path) or ".")
    if _panel_fingerprint(saved) != _panel_fingerprint(fresh):
        raise PanelError(f"{path} does not match the replies and flip.json beside it; rerun hc.py tally")
    if judges and fresh["judges"] != judges:
        raise PanelError(f"the panel has {fresh['judges']} judges; this run uses {judges}")
    return fresh


def _judge_prompt(row):
    jdir = os.path.abspath(row["dir"])
    with open(PROMPT, encoding="utf-8-sig") as f:
        text = f.read().rstrip("\n")
    sides = "\n".join(f"Version {s} is in {os.path.join(jdir, s)}: {', '.join(sorted(os.listdir(os.path.join(jdir, s))))}"
                      for s in ("A", "B"))
    return f"{text}\n\n{sides}\nDo not read any other file.\n"


def _call_judge(cmd, timeout, blind, row):
    """Run the judge command for one judge. Returns (receipt, stdout, error); the caller saves stdout unedited."""
    j = row["judge"]
    prompt = _judge_prompt(row)
    prompt_path = os.path.abspath(os.path.join(blind, f"judge-{j}.prompt.md"))
    with open(prompt_path, "w") as f:
        f.write(prompt)
    env = dict(os.environ, HC_JUDGE=str(j), HC_JUDGE_DIR=os.path.abspath(row["dir"]), HC_JUDGE_PROMPT=prompt_path)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, input=prompt.encode(), capture_output=True, cwd=row["dir"], env=env,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, None, f"judge {j}: timed out after {timeout:g}s"
    if p.returncode != 0:
        tail = (p.stderr or p.stdout).decode(errors="replace").strip()[-300:]
        return None, None, f"judge {j}: exit {p.returncode}: {tail}"
    if not _reply_verdict(p.stdout.decode("utf-8-sig", errors="replace")):
        return None, None, f"judge {j}: no 'VERDICT: A|B|TIE' line in its reply"
    return {"judge": j, "exit": 0, "seconds": round(time.time() - t0, 2),
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "reply_sha256": hashlib.sha256(p.stdout).hexdigest()}, p.stdout, None


def _set_aside(path):
    k = 1
    while os.path.exists(f"{path}.failed-{k}"):
        k += 1
    os.rename(path, f"{path}.failed-{k}")
    return f"{path}.failed-{k}"


def _judge_panel(run, best_dir, cand_dir, blind, caller, attempt=1):
    """Flip, call every judge, save the replies and the receipt, tally. The replies exist only because this
    function wrote them; a blind folder that is already there was not made by it and is refused."""
    cfg = run.cfg
    if os.path.exists(blind):
        raise PanelError(f"{blind} exists before hc.py called any judge, so a reply in it would be planted; "
                         f"hc.py writes the judge replies itself. Delete that folder")
    if not os.path.isfile(PROMPT):
        raise PanelError(f"{PROMPT} is missing; hc.py sends it to every judge")
    rows = _flip(cfg["judges"], best_dir, cand_dir, blind)
    with ThreadPoolExecutor(max_workers=len(rows)) as pool:
        results = list(pool.map(lambda row: _call_judge(cfg["judge_cmd"], cfg["timeout"], blind, row), rows))
    errors = [err for _, _, err in results if err]
    if errors:
        raise PanelError(f"{'; '.join(errors)} (set aside in {_set_aside(blind)})")
    # No reply touches the disk until every judge has answered, so nobody can watch a panel go one way and stop it.
    for receipt, reply, _ in results:
        with open(os.path.join(blind, f"judge-{receipt['judge']}.txt"), "wb") as f:
            f.write(reply)
    _save(os.path.join(blind, RECEIPT), {"caller": caller, "judge_cmd": cfg["judge_cmd"], "attempt": attempt,
                                         "prompt_sha256": _sha_file(PROMPT),
                                         "judges": [receipt for receipt, _, _ in results]})
    panel = _tally(blind)
    panel["attempt"] = attempt
    _save(os.path.join(blind, "panel.json"), panel)
    return panel


def _captures(folder):
    names = os.listdir(folder) if os.path.isdir(folder) else []
    return sorted(n for n in names if any(n.endswith(e) for e in FLIP_EXT.split(",")))


def _capture_hashes(folder):
    return {n: _sha_file(os.path.join(folder, n)) for n in _captures(folder)}


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


def _log_row(**fields):
    cmd_log(argparse.Namespace(file=LOG, quiet=True, fields=[f"{k}={v}" for k, v in fields.items()]))


def cmd_status(a):
    rows = _read(a.file)
    if not rows:
        sys.exit("status: no rounds logged yet")
    kept = [r for r in rows if r["verdict"].lower() in KEEP_VERDICTS]
    rounds = len(rows) - 1  # row 0 is the baseline
    since_win = _since_win(rows)
    stop = []
    if a.budget and rounds >= a.budget:
        stop.append(f"budget of {a.budget} rounds used")
    if a.patience and since_win >= a.patience:
        stop.append(f"{since_win} rounds without a win (patience {a.patience})")
    print(json.dumps({"rounds": rounds, "wins": len(kept) - 1, "rounds_since_win": since_win,
                      "baseline": rows[0]["score"], "best": kept[-1]["score"] if kept else None,
                      "best_round": kept[-1]["round"] if kept else None,
                      "stop": stop or None}, indent=1))


def _since_win(rows):
    since = 0
    for r in reversed(rows):
        if r["verdict"].lower() in KEEP_VERDICTS:
            break
        since += 1
    return since


def _wins(rows):
    return sum(r["verdict"].lower() == "keep" for r in rows)


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
    return _load(out)


def _shell(cmd, timeout):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"timed out: {cmd}"
    return None if r.returncode == 0 else f"{cmd}: exit {r.returncode}: {(r.stdout + r.stderr).strip()[-300:]}"


def _capture(cmd, folder, timeout):
    os.makedirs(folder, exist_ok=True)
    return _shell(f"{cmd} {shlex.quote(folder)}", timeout)


def _fresh_tree():
    """Drop Python bytecode caches. They are keyed on source mtime in whole seconds and on size, so a revert and
    the next edit landing in the same second can run the previous round's code."""
    for root, dirs, _ in os.walk("."):
        dirs[:] = [d for d in dirs if d not in (".git", ".hillclimb", "node_modules")]
        for d in list(dirs):
            path = os.path.join(root, d)
            if d == "__pycache__" and not _git("ls-files", "--", path).stdout.strip():
                shutil.rmtree(path, ignore_errors=True)
                dirs.remove(d)


def _settle_mtime():
    """Wait for the next whole second, so edits after a revert get a newer mtime than anything built before it."""
    time.sleep(1.02 - time.time() % 1.0)


def _reset_to(commit):
    _git("reset", "-q", "--hard", commit)
    _fresh_tree()
    _settle_mtime()


def _frozen_diff(cfg, *revs):
    if not cfg.get("frozen"):
        return []
    return _git("diff", "--name-only", *revs, "--", *cfg["frozen"]).stdout.split()


def _run_gates(cfg):
    for g in cfg.get("gates", []):
        try:
            r = subprocess.run(g, shell=True, capture_output=True, text=True, timeout=cfg["timeout"])
        except subprocess.TimeoutExpired:
            return f"gate timed out: {g}"
        if r.returncode != 0:
            return f"gate failed: {g}: {(r.stdout + r.stderr).strip()[-300:]}"
    return None


def _digest(path):
    """sha256 of a path's content, None if absent. Walks git-ignored files too: git cannot see them, a lock must."""
    if os.path.islink(path):
        target = _digest(os.path.realpath(path)) if os.path.exists(path) else None
        return hashlib.sha256(b"link\0" + os.readlink(path).encode() + b"\0" + str(target).encode()).hexdigest()
    if os.path.isfile(path):
        return _sha_file(path)
    if not os.path.isdir(path):
        return None
    h = hashlib.sha256(b"dir\0")
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_IN_LOCKS)
        for name in sorted(files + dirs):
            full = os.path.join(root, name)
            if name.endswith(".pyc"):
                continue
            if os.path.islink(full):
                body = _digest(full).encode()
            elif os.path.isfile(full):
                body = _sha_file(full).encode()
            else:
                continue
            h.update(os.path.relpath(full, path).encode() + b"\0" + body + b"\0")
    return h.hexdigest()


def _lock_paths(cfg):
    return {p: _digest(p) for p in dict.fromkeys(list(cfg.get("frozen", [])) + list(ALWAYS_LOCKED))}


def _lock_sum(paths):
    return hashlib.sha256(json.dumps(paths, sort_keys=True).encode()).hexdigest()


def _baseline_lock():
    for r in reversed(_read(LOG)):
        if r["verdict"].lower() == "baseline":
            m = re.search(r"lock ([0-9a-f]{12})", r.get("notes", ""))
            return m.group(1) if m else None
    return None


def _lock_changes():
    if not os.path.isfile(LOCKS):
        return ["locks.json missing (run hc.py baseline)"]
    locks = _load(LOCKS)
    if _lock_sum(locks.get("paths", {})) != locks.get("all") or _baseline_lock() != locks["all"][:12]:
        return ["locks.json changed since baseline"]
    return [p for p, h in sorted(locks["paths"].items()) if _digest(p) != h]


def _require_locks(run):
    if not run.v2:
        return
    changed = _lock_changes()
    if changed:
        raise Refused(f"REFUSED: frozen content changed: {', '.join(changed)}; restore it (git cannot restore "
                      f"ignored or untracked files) or restart with setup --force")


def _preflight_state():
    return _load(PREFLIGHT) if os.path.isfile(PREFLIGHT) else {}


def _preflight_done():
    pf = _preflight_state()
    return bool(pf.get("skip")) or bool(pf.get("broken", {}).get("pass") and pf.get("cheat", {}).get("pass"))


def _holdout_log():
    return _load(HOLDOUT) if os.path.isfile(HOLDOUT) else []


def _holdout_due():
    log = _holdout_log()
    return log[-1].get("pending") if log else None


def _overfit_stop():
    log = _holdout_log()
    last = log[-1] if log else {}
    if not last.get("overfit"):
        return None
    if last.get("visible_gain") is not None:
        numbers = f"visible {_pct(last['visible_gain'])}, holdout {_pct(last['holdout_gain'])}"
    else:
        numbers = f"{last['wins']} wins, holdout panel {last['score']}"
    return (f"STOP: overfitting: the visible score climbed but the holdout did not ({numbers}, holdout "
            f"{last['holdout_verdict']} at round {last['round']}). Report it; do not keep climbing.")


def cmd_setup(a):
    if not a.judges and not (a.cmd and a.direction):
        _refuse(2, "setup: --cmd and --direction are required (or --judges N for a judge run)")
    if a.judges is not None and a.judges < 1:
        _refuse(2, "setup: --judges must be 1 or more")
    if a.judge_cmd and not a.judges:
        _refuse(2, "setup: --judge-cmd needs --judges N")
    cmd_init(argparse.Namespace(dir="."))
    cfg = {"cmd": a.cmd, "regex": a.regex, "direction": a.direction, "min_delta": a.min_delta, "runs": a.runs,
           "warmup": a.warmup, "expect": a.expect, "expect_line": a.expect_line, "gates": a.gate,
           "frozen": a.frozen, "budget": a.budget, "patience": a.patience, "timeout": a.timeout,
           "version": FORMAT_VERSION, "judges": a.judges, "judge_cmd": a.judge_cmd, "holdout_cmd": a.holdout_cmd}
    if os.path.exists(CONFIG) and not a.force:
        sys.exit("setup: .hillclimb/config.json exists; the score never changes mid-run (use --force to restart "
                 "the run at a new round 0, and note why under Restarts in HILLCLIMB.md)")
    _save(CONFIG, cfg)
    print(json.dumps(cfg, indent=1))
    if not a.holdout_cmd and (a.judges or a.frozen):
        print("NOTE: no --holdout-cmd; the final number will be the score on the set you climbed on.")
    if a.judges and not a.judge_cmd:
        print("NOTE: no --judge-cmd; you will save the judges' replies yourself, and hc.py cannot check who wrote "
              "them. Give --judge-cmd when a headless model call is available.")
    print("NEXT: fill in .hillclimb/HILLCLIMB.md, commit any pending work, then run: hc.py baseline")


def _next(run, since_win, rounds, next_n):
    cfg = run.cfg
    stop = []
    if cfg["budget"] and rounds >= cfg["budget"]:
        stop.append(f"budget of {cfg['budget']} rounds used")
    if cfg["patience"] and since_win >= cfg["patience"]:
        stop.append(f"{since_win} rounds in a row without a win (patience {cfg['patience']})")
    if stop:
        return "STOP: " + "; ".join(stop) + ". Confirm the best against the baseline, then write the report."
    if run.judge_cmd:
        folder = os.path.join(ROUNDS, f"r{next_n:02d}")
        how = (f"capture into {folder}/, then run: hc.py round \"<what you changed>\" (it flips, calls the judges "
               f"and counts their votes).")
    elif run.v2 and run.judge:
        folder = os.path.join(ROUNDS, f"r{next_n:02d}")
        how = (f"capture into {folder}/, flip it against the best into {folder}/blind, save each judge's reply as "
               f"judge-J.txt there, run hc.py tally {folder}/blind, then: hc.py round \"<what you changed>\" "
               f"--panel {folder}/blind/panel.json.")
    else:
        how = "run: hc.py round \"<what you changed>\"."
    msg = (f"NEXT: round {rounds + 1} of {cfg['budget'] or 'unlimited'}. Make ONE change (not to frozen files) "
           f"and {how} The run is not over until this prints STOP; a big win is not a stop rule.")
    half = math.ceil(cfg["patience"] / 2) if cfg["patience"] and cfg["patience"] > 2 else 0
    if half and since_win == half:
        msg += " Big move due: try a different approach altogether, not a tweak (notes=big-move)."
    return msg


def _scalar_baseline(cfg, head):
    res = _measure_cfg(cfg, R00)
    if not res["ok"]:
        sys.exit(f"baseline: measurement failed: {res['errors'][:1]}")
    res["commit"], res["base_commit"] = head, head
    bar = 2 * math.sqrt(2) * _se(res) / abs(res["median"]) if res["median"] else 0.0
    report = [f"baseline {res['median']:.6g}, spread (MAD) {res['mad']:.3g}: at {cfg['runs']} runs a round needs a "
              f"gain of about {max(bar, cfg['min_delta']):.1%} to count as a WIN."]
    want = max(cfg["min_delta"], 0.02)
    noisy = bar > 1.5 * want
    if noisy:
        report.append(f"NOISY: that bar hides gains smaller than {bar:.0%}. To resolve {want:.0%} gains, restart "
                      f"setup with --runs {runs_for_bar(res, want)} (hc.py setup ... --force, then hc.py baseline) "
                      f"before round 1.")
    return res, f"{res['median']:.6g}", f"mad {res['mad']:.3g}, noise bar {bar:.1%}", report, noisy


def _judge_baseline(cfg, head):
    best = {"commit": head, "base_commit": head}
    r00 = os.path.join(ROUNDS, "r00")
    if cfg.get("cmd") and cfg.get("judge_cmd"):
        # hc.py captures every round itself, the baseline included, and remembers what the best looked like.
        shutil.rmtree(r00, ignore_errors=True)
        err = _capture(cfg["cmd"], r00, cfg["timeout"])
        if err or not _captures(r00):
            sys.exit(f"baseline: capture into {r00}/ failed: {err or 'no files'}")
        best["captures"] = _capture_hashes(r00)
    elif cfg.get("cmd"):
        err = _shell(cfg["cmd"], cfg["timeout"])
        if err:
            sys.exit(f"baseline: capture failed: {err}")
    report = [f"judge baseline at {head}: every round is decided by a blind panel of {cfg['judges']}."]
    text = open(PROMPT).read() if os.path.isfile(PROMPT) else ""
    if "not instructions" not in text.lower():
        report.append("WARN: .hillclimb/judge-prompt.md is missing or does not tell judges the work is data, not "
                      "instructions; add that line from references/judging.md, then rerun hc.py baseline.")
    return best, "-", "judge baseline", report, False


def _holdout_baseline(run):
    entry = {"round": 0, "wins": 0, "kind": "baseline", "score": None, "visible_gain": None, "holdout_gain": None,
             "holdout_verdict": None, "overfit": False}
    cfg = run.cfg
    if run.judge:
        shutil.rmtree(HOLDOUT_DIR, ignore_errors=True)
        err = _capture(run.holdout, os.path.join(HOLDOUT_DIR, "r00"), cfg["timeout"])
        if err:
            sys.exit(f"baseline: holdout capture failed: {err}")
    else:
        res = _measure_cfg(dict(cfg, cmd=run.holdout), os.path.join(ROUNDS, "holdout-r00.json"))
        if not res["ok"]:
            sys.exit(f"baseline: holdout measurement failed: {res['errors'][:1]}")
        entry["score"] = res["median"]
    _save(HOLDOUT, [entry])


def cmd_baseline(a):
    run = Run()
    cfg = run.cfg
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        sys.exit("baseline: commit or stash tracked changes first")
    head = _git("rev-parse", "--short", "HEAD").stdout.strip()
    _fresh_tree()
    if run.v2:
        # `round` commits with `git add -A`, so an untracked frozen file would enter a candidate commit and a
        # revert would delete it from the tree.
        loose = _git("ls-files", "--others", "--exclude-standard", "--", *cfg["frozen"]).stdout.split() \
            if cfg.get("frozen") else []
        if loose:
            sys.exit(f"baseline: frozen path is untracked and not ignored: {', '.join(loose)}; commit it or add it "
                     f"to .gitignore, or a reverted round would delete it")
        if os.path.exists(PREFLIGHT):
            os.remove(PREFLIGHT)
        locked = _lock_paths(cfg)
    err = _run_gates(cfg)
    if err:
        sys.exit(f"baseline: {err}. The gates must pass on the untouched version; fix the setup, not the gate.")
    best, score, notes, report, noisy = (_judge_baseline if run.judge else _scalar_baseline)(cfg, head)
    if run.holdout:
        _holdout_baseline(run)
    if run.v2:
        after = _lock_paths(cfg)
        changed = [p for p in locked if locked[p] != after[p]]
        if changed:
            sys.exit(f"baseline: the score command or a gate changed frozen content: {', '.join(changed)}")
        locks = {"paths": locked, "all": _lock_sum(locked)}
        _save(LOCKS, locks)
        notes += f", lock {locks['all'][:12]}"
    _save(BEST, best)
    _log_row(round=0, change="baseline", score=score, gates="pass", verdict="baseline", notes=notes)
    print("\n".join(report))
    if noisy:
        return
    if run.v2:
        print("PRE-FLIGHT: before round 1, break the work on purpose and run hc.py preflight broken, restore it; "
              "change one frozen path and run hc.py preflight cheat, restore it.")
    print(_next(run, 0, 0, len(_read(LOG))))


def _round_refusal(run, a):
    """Reasons to refuse before anything is committed (exit 2)."""
    if a.verdict and a.panel:
        return "round: give --panel or --verdict, not both"
    if run.judge_cmd and (a.verdict or a.panel):
        return JUDGE_CMD_REFUSAL.format(what="round", how="capture into the round's folder and run hc.py round "
                                                          "\"<change>\" with no --panel")
    if run.v2 and (a.verdict or (run.judge and not run.judge_cmd and not a.panel)):
        return VERDICT_REFUSAL
    if run.v2 and a.panel and not run.judge:
        return "round: --panel is for judge runs (setup --judges N); a scalar round is measured"
    if a.panel:
        try:
            a.tallied = _round_panel(run, a.panel, len(_read(LOG)))
        except PanelError as e:
            return f"round: {e}; nothing was committed, fix the panel and run the same round again"
    if not run.v2:
        return None
    if not _preflight_done():
        return PREFLIGHT_REFUSAL
    due = _holdout_due()
    if due:
        return (f"round: holdout check due; judge {due}, save each reply as judge-J.txt there, run hc.py tally "
                f"{due}, then hc.py holdout --panel {os.path.join(due, 'panel.json')}")
    if run.judge_cmd:
        return _judged_round_refusal(run.cfg, len(_read(LOG)))
    return None


def _best_round():
    """The round whose captures are the best's: the last kept row (the baseline is round 0)."""
    return int([r for r in _read(LOG) if r["verdict"].lower() in KEEP_VERDICTS][-1]["round"])


def _judged_round_refusal(cfg, n):
    folder = os.path.join(ROUNDS, f"r{n:02d}")
    best = os.path.join(ROUNDS, f"r{_best_round():02d}")
    kept = _load(BEST).get("captures")
    if not os.path.isfile(PROMPT):
        return f"round: {PROMPT} is missing; hc.py sends it to every judge"
    if not _captures(best):
        return f"round: the best's captures are missing from {best}/; hc.py flips the candidate against them"
    if kept and _capture_hashes(best) != kept:
        return (f"round: the best's captures in {best}/ changed since that round was kept; restore them or restart "
                f"with setup --force")
    if cfg.get("cmd"):
        if os.path.exists(folder):
            return (f"round: {folder}/ exists, but hc.py captures the candidate itself with the setup --cmd; delete "
                    f"it and run the same round again; nothing was committed")
    elif not _captures(folder):
        return f"round: capture the candidate into {folder}/ first; nothing was committed"
    elif _captures(folder) != _captures(best):
        return (f"round: {folder}/ holds {', '.join(_captures(folder))} but the best has "
                f"{', '.join(_captures(best))}; capture the same views, nothing else; nothing was committed")
    if os.path.exists(os.path.join(folder, "blind")):
        return (f"round: {folder}/blind exists before hc.py called any judge, so a reply in it would be planted; "
                f"hc.py writes the judge replies itself. Delete {folder}/blind and run the same round again; "
                f"nothing was committed")
    return None


def _round_panel(run, path, n):
    blind = os.path.normpath(os.path.join(ROUNDS, f"r{n:02d}", "blind"))
    want = os.path.join(blind, "panel.json")
    if _rel(path) != want:
        raise PanelError(f"{path} is not this round's panel; round {n} reads {want}")
    panel = _verify_panel(path, run.cfg.get("judges"))
    # flip records each judge's folder, so a blind folder copied from another round still names that round.
    for row in _load(os.path.join(blind, "flip.json")):
        if _rel(row.get("dir", "")) != os.path.join(blind, f"judge-{row['judge']}"):
            raise PanelError(f"flip.json in {blind} was made for another folder ({row.get('dir')}); "
                             f"run hc.py flip --out {blind} for this round")
    return panel


def _measured(cfg, n):
    out = os.path.join(ROUNDS, f"r{n:02d}.json")
    cand = _measure_cfg(cfg, out)
    if not cand["ok"]:
        return "LOSS", "", f"measurement failed: {cand['errors'][:1]}", "fail"
    c = _compare(_load(BEST), cand, cfg["direction"], cfg["min_delta"])
    return c["verdict"], f"{cand['median']:.6g}", f"gain {c['gain_rel']:+.1%}, bar {c['bar_rel']:.1%}", "pass"


def _score_round(run, a, best, n):
    """Judge one committed candidate: (verdict, score, notes, gates). Raises Refused."""
    cfg = run.cfg
    changed = _frozen_diff(cfg, best["base_commit"], "HEAD")
    if changed:
        return "LOSS", "", f"frozen file changed: {', '.join(changed)}", "fail"
    _require_locks(run)
    err = _run_gates(cfg)
    if err:
        result = ("LOSS", "", err, "fail")
    elif a.panel:
        panel = a.tallied
        result = (panel["verdict"], panel["score"], f"panel {panel['score']}", "pass")
    elif run.judge_cmd:
        result = _judged(run, best, n)
    elif a.verdict:
        result = (a.verdict.upper(), a.score or "", a.notes or "", "pass")
    else:
        result = _measured(cfg, n)
    _require_locks(run)
    return result


def _judged(run, best, n):
    """Capture (when the run has a capture command), flip against the best's captures, call the judges, tally."""
    cfg = run.cfg
    folder, best_dir = os.path.join(ROUNDS, f"r{n:02d}"), os.path.join(ROUNDS, f"r{_best_round():02d}")
    if "captures" not in best:
        # The agent captured the baseline after `baseline` ran; from here on it cannot change unnoticed.
        best["captures"] = _capture_hashes(best_dir)
        _save(BEST, best)
    if cfg.get("cmd"):
        err = _capture(cfg["cmd"], folder, cfg["timeout"])
        if err:
            return "LOSS", "", f"capture failed: {err}", "fail"
        if _captures(folder) != sorted(best["captures"]):
            return "LOSS", "", f"capture made {', '.join(_captures(folder)) or 'no files'}, not the best's views", "fail"
    # Failed attempts are set aside, never deleted, so the log can say how many panels this round took.
    attempt = 1 + len([f for f in os.listdir(ROUNDS) if f.startswith(f"r{n:02d}.failed-")]) + \
        len([f for f in os.listdir(folder) if f.startswith("blind.failed-")])
    try:
        panel = _judge_panel(run, best_dir, folder, os.path.join(folder, "blind"), f"hc.py round r{n:02d}", attempt)
    except PanelError as e:
        if cfg.get("cmd"):  # hc.py captures again on the rerun, so the whole folder goes aside
            raise PanelError(f"{e}; {folder} set aside as {_set_aside(folder)}")
        raise
    tries = f", attempt {panel['attempt']}" if panel["attempt"] > 1 else ""
    return panel["verdict"], panel["score"], f"panel {panel['score']}, judges called by hc.py{tries}", "pass"


def _holdout_check(run, n, wins, kind):
    """Score the best on the holdout. Returns an error line, or None once the check is recorded or due."""
    cfg = run.cfg
    entry = {"round": n, "wins": wins, "kind": kind, "score": None, "visible_gain": None, "holdout_gain": None,
             "holdout_verdict": None, "overfit": False}
    if run.judge:
        folder = os.path.join(HOLDOUT_DIR, f"r{n:02d}")
        if os.path.exists(folder):
            return f"HOLDOUT: {folder} is already taken; record it with hc.py holdout --panel"
        err = _capture(run.holdout, os.path.join(folder, "cand"), cfg["timeout"])
        if err:
            return f"HOLDOUT: capture failed, no check taken: {err}"
        blind = os.path.join(folder, "blind")
        if run.judge_cmd:
            try:
                panel = _judge_panel(run, os.path.join(HOLDOUT_DIR, "r00"), os.path.join(folder, "cand"), blind,
                                     caller=f"hc.py holdout r{n:02d} ({kind})")
            except PanelError as e:
                return f"HOLDOUT: no check taken: {e}; run hc.py holdout at the best to take it ({_set_aside(folder)})"
            _apply_holdout_panel(entry, panel)
            _save(HOLDOUT, _holdout_log() + [entry])
            return None
        _flip(cfg["judges"], os.path.join(HOLDOUT_DIR, "r00"), os.path.join(folder, "cand"), blind)
        entry["pending"] = blind
        print(f"HOLDOUT ({kind}): due. Run {cfg['judges']} fresh judges on {blind}/judge-J, save each full reply as "
              f"{blind}/judge-J.txt, run hc.py tally {blind}, then hc.py holdout --panel {blind}/panel.json. "
              f"The next round is refused until then.")
    else:
        res = _measure_cfg(dict(cfg, cmd=run.holdout), os.path.join(ROUNDS, f"holdout-r{n:02d}.json"))
        if not res["ok"]:
            return f"HOLDOUT: measurement failed, no check taken: {res['errors'][:1]}"
        visible = _compare(_load(R00), _load(BEST), cfg["direction"], cfg["min_delta"])
        held = _compare(_load(os.path.join(ROUNDS, "holdout-r00.json")), res, cfg["direction"], cfg["min_delta"])
        entry.update(score=res.get("median"), visible_gain=visible.get("gain_rel"),
                     holdout_gain=held.get("gain_rel"), holdout_verdict=held["verdict"],
                     overfit=visible["verdict"] == "WIN" and held["verdict"] != "WIN")
        print(f"HOLDOUT ({kind}): visible {_pct(entry['visible_gain'])} ({visible['verdict']}), "
              f"holdout {_pct(entry['holdout_gain'])} ({held['verdict']})")
    _save(HOLDOUT, _holdout_log() + [entry])
    return None


def cmd_round(a):
    run = Run()
    cfg = run.cfg
    early = _round_refusal(run, a)
    if early:
        _refuse(2, early)
    best = _load(BEST)
    n = len(_read(LOG))
    start = _git("rev-parse", "HEAD").stdout.strip()
    _fresh_tree()
    _git("add", "-A")
    if _git("diff", "--cached", "--quiet").returncode != 0:
        _git("commit", "-q", "-m", f"r{n:02d}: {a.change}")
    head = _git("rev-parse", "--short", "HEAD").stdout.strip()
    if _git("rev-parse", "HEAD").stdout.strip() == _git("rev-parse", best["commit"]).stdout.strip():
        sys.exit("round: nothing changed since the best; make one change first")
    try:
        verdict, score, notes, gates = _score_round(run, a, best, n)
    except Refused as r:
        _log_row(round=n, commit=head, change=a.change, score="", gates="-", verdict="refused", notes=str(r))
        _reset_to(best["commit"])
        print(r)
        sys.exit(3)
    except PanelError as e:
        # A judge that failed (a timeout, a crash, no verdict line) says nothing about the work: undo the commit,
        # keep the change in the tree, log nothing, so the same round can run again.
        _git("reset", "-q", "--soft", start)
        _refuse(2, f"round: the judges did not all reply: {e}. Nothing was logged and the round's commit was "
                   f"undone; the change is still in the tree, so run the same round again")
    if verdict == "NOISE" and a.simpler and not a.verdict:
        verdict, notes = "KEEP", notes + ", simpler"
    if a.notes and not a.verdict:
        notes = f"{notes}, {a.notes}" if notes else a.notes
    keep = verdict in ("WIN", "KEEP")
    _log_row(round=n, commit=head, change=a.change, score=score, gates=gates,
             verdict="keep" if keep else "revert", notes=f"{verdict}: {notes[:200]}")
    if keep:
        measured = not (a.verdict or a.panel or run.judge_cmd)
        new = _load(os.path.join(ROUNDS, f"r{n:02d}.json")) if measured else dict(best)
        new["commit"], new["base_commit"] = head, best["base_commit"]
        if run.judge_cmd:
            new["captures"] = _capture_hashes(os.path.join(ROUNDS, f"r{n:02d}"))
        _save(BEST, new)
    else:
        _reset_to(best["commit"])
    rows = _read(LOG)
    wins = _wins(rows)
    print(f"{verdict}: {notes}" + (" -> kept" if keep else f" -> reverted to {best['commit']}"))
    line = _next(run, _since_win(rows), len(rows) - 1, len(rows))
    if run.holdout:
        kind = "final" if line.startswith("STOP") else "check" if keep and wins % 5 == 0 else None
        err = _holdout_check(run, n, wins, kind) if kind else None
        if err:
            print(err)
        line = _overfit_stop() or line
    print(line)


def _at_best(best):
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        return False
    return _git("rev-parse", "HEAD").stdout.strip() == _git("rev-parse", best["commit"]).stdout.strip()


def _apply_holdout_panel(entry, panel):
    entry.update(score=panel["score"], holdout_verdict=panel["verdict"],
                 overfit=entry["wins"] > 0 and panel["verdict"] != "WIN")
    print(f"HOLDOUT ({entry['kind']}): panel {panel['score']} -> {panel['verdict']}")


def _record_holdout_panel(run, path):
    log = _holdout_log()
    due = log[-1].get("pending") if log else None
    if not due:
        _refuse(2, "holdout: no judged holdout check is due")
    want = os.path.normpath(os.path.join(due, "panel.json"))
    if _rel(path) != want:
        _refuse(2, f"holdout: the due check reads {want}")
    try:
        panel = _verify_panel(path, run.cfg["judges"])
    except PanelError as e:
        sys.exit(f"holdout: {e}")
    last = log[-1]
    last.pop("pending")
    _apply_holdout_panel(last, panel)
    _save(HOLDOUT, log)
    after = "the run had stopped; write the report." if last["kind"] == "final" else "continue with the next round."
    print(_overfit_stop() or f"NEXT: holdout recorded; {after}")


def cmd_holdout(a):
    run = Run()
    if not run.holdout:
        _refuse(2, "holdout: this run has no --holdout-cmd")
    if a.panel and run.judge_cmd:
        _refuse(2, JUDGE_CMD_REFUSAL.format(what="holdout", how="hc.py judges each holdout check when it is taken"))
    if a.panel:
        _record_holdout_panel(run, a.panel)
        return
    if _holdout_due():
        _refuse(2, f"holdout: a check is already due; judge {_holdout_due()} and record it with --panel")
    if not _at_best(_load(BEST)):
        _refuse(2, "holdout: the tree is not at the best commit; commit, revert or stash first")
    rows = _read(LOG)
    err = _holdout_check(run, len(rows) - 1, _wins(rows), "check")
    if err:
        _refuse(2, err)
    stop = _overfit_stop()
    if stop:
        print(stop)


def _preflight_broken(run, panel):
    cfg = run.cfg
    if run.judge_cmd:
        return _preflight_broken_judged(run, panel)
    if run.judge:
        root = os.path.normpath(os.path.join(ROUNDS, "preflight")) + os.sep
        if not panel or not _rel(panel).startswith(root) or os.path.basename(panel) != "panel.json":
            _refuse(2, f"preflight broken: a judge run needs --panel {root}<name>/blind/panel.json, best = the "
                       f"baseline captures, candidate = the broken version")
        try:
            p = _verify_panel(panel, cfg["judges"])
        except PanelError as e:
            sys.exit(f"preflight: {e}")
        return {"pass": p["verdict"] == "LOSS", "why": f"panel {p['score']}, {p['verdict']}", "panel": panel}
    if panel:
        _refuse(2, "preflight broken: --panel is for judge runs; a scalar run is measured")
    _fresh_tree()
    err = _run_gates(cfg)
    if err:
        return {"pass": True, "why": err}
    res = _measure_cfg(cfg, os.path.join(ROUNDS, "preflight-broken.json"))
    if not res["ok"]:
        return {"pass": True, "why": f"measurement failed: {res['errors'][:1]}"}
    c = _compare(_load(R00), res, cfg["direction"], cfg["min_delta"])
    return {"pass": c["verdict"] == "LOSS", "why": f"gain {c['gain_rel']:+.1%}, {c['verdict']}"}


def _preflight_broken_judged(run, panel):
    if panel:
        _refuse(2, JUDGE_CMD_REFUSAL.format(what="preflight broken", how="capture the broken version into "
                                                                     ".hillclimb/rounds/preflight/cand/ and run "
                                                                     "hc.py preflight broken with no --panel"))
    root = os.path.join(ROUNDS, "preflight")
    best, cand, blind = os.path.join(ROUNDS, "r00"), os.path.join(root, "cand"), os.path.join(root, "blind")
    for folder, what in ((best, "the baseline"), (cand, "the broken version")):
        if not _captures(folder):
            _refuse(2, f"preflight broken: capture {what} into {folder}/ first")
    # The pre-flight may be retried; an earlier blind folder is replaced, never read.
    if os.path.exists(blind):
        _set_aside(blind)
    try:
        p = _judge_panel(run, best, cand, blind, caller="hc.py preflight broken")
    except PanelError as e:
        sys.exit(f"preflight: {e}")
    return {"pass": p["verdict"] == "LOSS", "why": f"panel {p['score']}, {p['verdict']}, judges called by hc.py",
            "panel": os.path.join(blind, "panel.json")}


def _preflight_cheat(run):
    changed = _frozen_diff(run.cfg, "HEAD") + (_lock_changes() if run.v2 else [])
    changed = list(dict.fromkeys(changed))
    return {"pass": bool(changed), "why": ", ".join(changed) or "no frozen change seen"}


def cmd_preflight(a):
    run = Run()
    if not os.path.isfile(BEST):
        _refuse(2, "preflight: run hc.py baseline first")
    pf = _preflight_state()
    if a.step == "skip":
        if not a.why:
            _refuse(2, "preflight skip: give the reason with --why \"...\"")
        pf["skip"] = a.why
        _save(PREFLIGHT, pf)
        print(f"pre-flight skipped: {a.why}")
        return
    result = _preflight_broken(run, a.panel) if a.step == "broken" else _preflight_cheat(run)
    pf[a.step] = result
    _save(PREFLIGHT, pf)
    if a.step == "broken" and result["pass"]:
        dirty = _git("status", "--porcelain").stdout.rstrip()
        print(f"PASS: the measure saw the broken version ({result['why']}). Restore these before round 1:\n"
              f"{dirty or '(nothing to restore)'}")
    elif a.step == "broken":
        print(f"{BROKEN_FAIL} ({result['why']})")
    elif result["pass"]:
        print(f"PASS: the change to {result['why']} was caught. Restore it before round 1.")
    else:
        print("FAIL: no frozen change was seen; change one --frozen path or .hillclimb/judge-prompt.md on purpose, "
              "then run it again.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="sub", required=True)

    s = sub.add_parser("setup")
    s.add_argument("--cmd", help="the scoring command, run from the repo root (judge runs: the capture command)")
    s.add_argument("--regex", help="metric = group 1 of the last match; omit to score the command's wall time")
    s.add_argument("--direction", choices=["min", "max"])
    s.add_argument("--judges", type=int, help="a judge run: rounds are decided by a blind panel of N judges")
    s.add_argument("--judge-cmd", help="judge runs: a shell command hc.py runs once per judge (prompt on stdin, cwd "
                                       "and $HC_JUDGE_DIR the judge's blind folder); its stdout is saved as the "
                                       "reply, so the climbing agent never writes one")
    s.add_argument("--holdout-cmd", help="score command over held-out data the builder never opens (judge runs: "
                                         "captures held-out views into the folder appended as its last argument)")
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
    s.add_argument("--panel", help="judge runs without --judge-cmd: this round's .hillclimb/rounds/rNN/blind/panel.json "
                                   "from hc.py tally")
    s.add_argument("--verdict", choices=["WIN", "LOSS", "NOISE", "win", "loss", "noise"],
                   help="legacy runs only: the unblinded panel verdict, decided outside this script")
    s.add_argument("--score", help="legacy runs with --verdict: the vote, e.g. '3/3 cand'")
    s.add_argument("--simpler", action="store_true", help="the change deletes more than it adds: keep it at equal score")
    s.add_argument("--notes")
    s.set_defaults(fn=cmd_round)

    s = sub.add_parser("tally")
    s.add_argument("dir", help="the blind folder: flip.json plus each judge's reply as judge-J.txt")
    s.set_defaults(fn=cmd_tally)

    s = sub.add_parser("preflight")
    s.add_argument("step", choices=["broken", "cheat", "skip"])
    s.add_argument("--panel", help="judge runs, broken: a panel under .hillclimb/rounds/preflight/")
    s.add_argument("--why", help="skip: the reason, kept in the record")
    s.set_defaults(fn=cmd_preflight)

    s = sub.add_parser("holdout")
    s.add_argument("--panel", help="judge runs: record the due holdout check's panel.json")
    s.set_defaults(fn=cmd_holdout)

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
    s.add_argument("--ext", default=FLIP_EXT, help="comma-separated file endings to copy")
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
