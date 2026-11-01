"""Run the hill-climb blind pairwise judge protocol on headline pairs with a known click-rate winner.

    python bench/taste/judge.py --model sonnet --judges 3

Each judge is a fresh, tool-less Claude Code call that sees two headlines as A and B, with its own coin flip
for which side holds the real winner, exactly as `hc.py flip` assigns sides. Verdicts land in
bench/taste/verdicts-<model>.jsonl, one line per judge call, and calls already made are skipped.
"""
import argparse
import json
import os
import random
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE = os.environ.get("CLAUDE_BIN", str(Path.home() / ".local/bin/claude"))

PROMPT = """You are judging two headlines for the same story on a news site that shares uplifting and \
social-issue stories, labelled A and B. Both ran with the same image and the same summary; only the \
headline differs. Readers see one of them in their feed and decide whether to click.

Score A and B from 1 to 10 on each axis, with one line of evidence per score that points at specific words:

1. How strongly it makes a typical reader want to click
2. Clarity: whether a reader can tell what the story is about
3. Emotional pull

Then give an overall verdict: which headline would get more clicks? Answer A, B, or TIE. Choose TIE only \
if you cannot tell them apart in a way that matters. Be decisive otherwise. Reply in this exact form:

AXES
A: <score 1>, <score 2>, <score 3>
B: <score 1>, <score 2>, <score 3>
EVIDENCE
- ...
VERDICT: A | B | TIE

A: {a}
B: {b}
"""

ISOLATION = ["--setting-sources", "project", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
             "--tools", "", "--disable-slash-commands", "--no-session-persistence",
             "--settings", json.dumps({"claudeMdExcludes": [str(Path.home() / ".claude/CLAUDE.md"),
                                                            str(Path.home() / ".claude-accounts/**")],
                                       "autoMemoryEnabled": False})]


def call(model, text):
    env = dict(os.environ)
    env.pop("CLAUDECODE", None)
    r = subprocess.run([CLAUDE, "-p", text, "--model", model, "--output-format", "json", *ISOLATION],
                       capture_output=True, text=True, timeout=300, cwd="/tmp", env=env)
    out = json.loads(r.stdout)["result"]
    m = re.findall(r"VERDICT:\s*\**\s*(A|B|TIE)\b", out)
    return (m[-1] if m else "PARSE"), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--judges", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    pairs = [json.loads(l) for l in open(HERE / "pairs.jsonl")]
    out_path = HERE / f"verdicts-{a.model}.jsonl"
    done = set()
    if out_path.exists():
        for l in open(out_path):
            v = json.loads(l)
            done.add((v["pair"], v["judge"]))
    rng = random.Random(f"flip-{a.model}")
    jobs = []
    for i, p in enumerate(pairs):
        for j in range(a.judges):
            winner_is_a = rng.random() < 0.5
            if (i, j) not in done:
                jobs.append((i, j, winner_is_a, p))

    def one(job):
        i, j, winner_is_a, p = job
        a_text, b_text = (p["winner"], p["loser"]) if winner_is_a else (p["loser"], p["winner"])
        verdict, raw = call(a.model, PROMPT.format(a=a_text, b=b_text))
        picked = None if verdict in ("TIE", "PARSE") else ((verdict == "A") == winner_is_a)
        return {"pair": i, "judge": j, "winner_side": "A" if winner_is_a else "B", "verdict": verdict,
                "picked_winner": picked, "raw": raw}

    with ThreadPoolExecutor(a.jobs) as pool, open(out_path, "a") as f:
        for rec in pool.map(one, jobs):
            f.write(json.dumps(rec) + "\n")
            f.flush()
    print(f"{len(jobs)} judge calls written to {out_path.name}")


if __name__ == "__main__":
    main()
