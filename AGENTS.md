# AGENTS.md

Instructions for a coding agent that has been handed this repository.

## What this repo is

One agent skill, `hill-climb`, in `skills/hill-climb/`. It teaches you to improve something over many rounds:
make one change, score it against the current best, keep it or revert it with git, log the round, and stop
on a budget. It covers number-scored work (speed, size, loss) and taste work (UI, copy) scored by blind judges.

## Install it

Pick the line that matches your harness, run it, then verify.

- **Claude Code, as a plugin** (the user types these in Claude Code):
  ```
  /plugin marketplace add abhaymettu/hill-climb
  /plugin install hill-climb@hill-climb
  ```
- **Claude Code, as a plain skill** (you can run this yourself):
  ```sh
  git clone https://github.com/abhaymettu/hill-climb /tmp/hill-climb
  mkdir -p ~/.claude/skills && cp -R /tmp/hill-climb/skills/hill-climb ~/.claude/skills/
  ```
  For one project only, copy into `<project>/.claude/skills/` instead.
- **Any other agent that reads skill folders** (a `SKILL.md` with YAML front matter): copy
  `skills/hill-climb/` into that agent's skills directory. If your agent has no skill system, read
  `skills/hill-climb/SKILL.md` at the start of the task and follow it.

Verify:

```sh
python3 ~/.claude/skills/hill-climb/scripts/hc.py -h     # prints the six subcommands
```

Requirements: `git` and Python 3.8 or newer. The helper uses the standard library only. Judge mode also needs
a way to start fresh-context model calls (subagents, or a headless CLI call) and whatever renders the
artifacts being judged (for web pages, a headless browser).

## Use it

When the user asks to hill-climb, optimize over rounds, or "keep improving X until...", read
`skills/hill-climb/SKILL.md` in full and follow it. In short:

1. Agree the score with the user in one sentence if they did not give one.
2. `python3 <skill>/scripts/hc.py init` in the target repo, fill in `.hillclimb/HILLCLIMB.md`, measure round 0.
3. Run rounds: one change, gates, score, log, keep or `git reset --hard HEAD~1`.
4. Stop on the budget or the patience rule and report best vs baseline.

`examples/` holds two complete runs (a 370x speed-up scored by a benchmark, and a page polished by blind
judges) with their setup files and logs. Read one if you want to see what a finished run looks like.

## Do not

- Change the score, gates or judge prompt after round 1 without logging a restart.
- Edit the benchmark, tests or judge prompt to make a number move.
- Push, publish or deploy as part of a run. The skill works on a local branch; shipping is the user's call.
