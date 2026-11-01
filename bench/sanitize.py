"""Strip the operator's machine details from transcripts before they are published.

    python bench/sanitize.py

The session's init event keeps only model, tools, cwd and version (it otherwise lists the account's agents and
commands). Any tool output that shows a path in the home directory outside this repo is replaced, and such paths
in the agent's own commands are masked. Idempotent.
"""
import gzip
import json
import re
from pathlib import Path

RUNS = Path(__file__).resolve().parent / "runs"
OUTSIDE = re.compile(r"/Users/abhay/(?!code/hill-climb/)[^\s\"'\\:;|]*|~/[A-Za-z.][A-Za-z0-9_./*-]*")
SUSPECT = re.compile(r"<redacted>|\bps\b|\bpgrep\b|\btop\b|\$HOME|\bfind /")
KEEP_INIT = {"type", "subtype", "model", "cwd", "tools", "claude_code_version", "session_id", "permissionMode"}


def clean(obj):
    if isinstance(obj, str):
        return OUTSIDE.sub("~/<redacted>", obj)
    if isinstance(obj, list):
        return [clean(x) for x in obj]
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    return obj


def clean_event(e):
    if e.get("type") == "system" and e.get("subtype") == "init":
        return {k: v for k, v in e.items() if k in KEEP_INIT}
    if e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), list):
        for c in e["message"]["content"]:
            if c.get("type") == "tool_result" and OUTSIDE.search(json.dumps(c.get("content"))):
                c["content"] = "[output redacted: it listed files outside the benchmark]"
    return clean(e)


def main():
    for f in sorted(RUNS.glob("*/transcript.jsonl.gz")):
        lines = gzip.open(f, "rt").read().splitlines()
        out, suspect = [], set()
        for line in lines:
            try:
                e = json.loads(line)
                if e.get("type") == "assistant":
                    for c in e["message"].get("content", []):
                        if c.get("type") == "tool_use" and (SUSPECT.search(json.dumps(c.get("input")))
                                                            or OUTSIDE.search(json.dumps(c.get("input")))):
                            suspect.add(c["id"])
                if e.get("type") == "user" and isinstance(e.get("message", {}).get("content"), list):
                    for c in e["message"]["content"]:
                        if c.get("type") == "tool_result" and c.get("tool_use_id") in suspect:
                            c["content"] = "[output redacted: it listed files or processes outside the benchmark]"
                            e["tool_use_result"] = c["content"]
                out.append(json.dumps(clean_event(e)))
            except json.JSONDecodeError:
                out.append(OUTSIDE.sub("~/<redacted>", line))
        with gzip.open(f, "wt") as g:
            g.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
