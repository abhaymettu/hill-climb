"""Run one agent on one task under one arm, with a fixed budget, in an isolated Claude Code session.

    python bench/run.py --task logstats --arm hillclimb --seed 1

The agent gets a fresh git repo holding the task's workspace. Nothing from the user's own Claude setup
reaches it: no CLAUDE.md, no user settings, hooks, plugins, skills or MCP servers. The hillclimb arm differs
from the loop arm only by the hill-climb plugin and one sentence asking it to use the skill.
Raw output lands in bench/runs/<task>-<arm>-s<seed>/.
"""
import argparse
import gzip
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
REPO = BENCH.parent
CLAUDE = os.environ.get("CLAUDE_BIN", str(Path.home() / ".local/bin/claude"))

CLAIM = ("When you finish, leave your final version in the working tree and write CLAIM.json in the repo "
         "root: {{\"metric\": \"{metric}\", \"baseline\": <number you measured before changing anything>, "
         "\"final\": <number you measured for your final version>, \"summary\": \"<one line>\"}}.")

ARMS = {
    "plain": "{prompt}\n\n{claim}",
    "loop": ("{prompt}\n\nWork in a loop: make a change, run the measurement, and keep improving for as many "
             "iterations as you can. Do not stop early.\n\n{claim}"),
    "hillclimb": "{prompt}\n\nUse the hill-climb skill for this.\n\n{claim}",
}


def isolation_args(arm, skill_dir):
    settings = {"claudeMdExcludes": [str(Path.home() / ".claude/CLAUDE.md"), str(Path.home() / ".claude-accounts/**")],
                "autoMemoryEnabled": False}
    args = ["--setting-sources", "project", "--settings", json.dumps(settings),
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--tools", "Bash,Read,Edit,Write,Glob,Grep,Skill",
            "--dangerously-skip-permissions", "--no-session-persistence"]
    if arm.startswith("hillclimb"):
        args += ["--plugin-dir", str(skill_dir)]
    return args


def git(ws, *a):
    subprocess.run(["git", "-C", str(ws), *a], check=True, capture_output=True)


def setup_workspace(task, ws):
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(BENCH / "tasks" / task / "workspace", ws,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    if task == "tinyclf":
        hidden = BENCH / "tasks" / task / "hidden"
        subprocess.run([str(BENCH / ".venv/bin/python"), str(hidden / "gen.py"), str(ws), str(hidden)], check=True)
    (ws / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "-c", "user.name=bench", "-c", "user.email=bench@localhost", "commit", "-q", "-m", "baseline")
    git(ws, "tag", "baseline")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--arm", required=True, choices=sorted(ARMS) + ["hillclimb-v2"])
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--budget-usd", type=float, default=4.0)
    ap.add_argument("--timeout-min", type=float, default=40)
    ap.add_argument("--skill-dir", default=str(REPO))
    a = ap.parse_args()

    run_id = f"{a.task}-{a.arm}-s{a.seed}" + ("" if a.model == "sonnet" else f"-{a.model}")
    out = BENCH / "runs" / run_id
    ws = BENCH / "work" / run_id / "ws"
    out.mkdir(parents=True, exist_ok=True)
    setup_workspace(a.task, ws)

    spec = json.loads((BENCH / "tasks" / a.task / "task.json").read_text())
    template = ARMS["hillclimb" if a.arm.startswith("hillclimb") else a.arm]
    prompt = template.format(prompt=spec["prompt"], claim=CLAIM.format(metric=spec["metric"]))

    env = dict(os.environ)
    env["PATH"] = f"{BENCH / '.venv/bin'}:{env['PATH']}"
    env["VIRTUAL_ENV"] = str(BENCH / ".venv")
    env.pop("CLAUDECODE", None)

    cmd = [CLAUDE, "-p", prompt, "--model", a.model, "--max-budget-usd", str(a.budget_usd),
           "--output-format", "stream-json", "--verbose", *isolation_args(a.arm, a.skill_dir)]
    t0 = time.time()
    timed_out = False
    with gzip.open(out / "transcript.jsonl.gz", "wt") as tf:
        proc = subprocess.Popen(cmd, cwd=ws, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            for line in proc.stdout:
                tf.write(line)
                if time.time() - t0 > a.timeout_min * 60:
                    timed_out = True
                    proc.kill()
                    break
        finally:
            proc.wait()
    wall = time.time() - t0

    result = {}
    with gzip.open(out / "transcript.jsonl.gz", "rt") as tf:
        for line in tf:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                result = ev
    subprocess.run(["git", "-C", str(ws), "add", "-A"], capture_output=True)
    diff = subprocess.run(["git", "-C", str(ws), "diff", "--cached", "baseline", "--", ".", ":!data"],
                          capture_output=True, text=True).stdout
    (out / "final.diff").write_text(diff)
    claim = ws / "CLAIM.json"
    if claim.exists():
        shutil.copy(claim, out / "claim.json")
    hc_log = ws / ".hillclimb" / "results.tsv"
    if hc_log.exists():
        shutil.copy(hc_log, out / "hillclimb-results.tsv")
    meta = {"task": a.task, "arm": a.arm, "seed": a.seed, "model": a.model, "budget_usd": a.budget_usd,
            "wall_seconds": round(wall, 1), "timed_out": timed_out, "exit": proc.returncode,
            "num_turns": result.get("num_turns"), "cost_usd": result.get("total_cost_usd"),
            "subtype": result.get("subtype"), "usage": result.get("usage"), "prompt": prompt}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps({k: meta[k] for k in ("task", "arm", "seed", "wall_seconds", "num_turns", "cost_usd", "subtype")}))


if __name__ == "__main__":
    main()
