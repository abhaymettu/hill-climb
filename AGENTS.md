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
python3 ~/.claude/skills/hill-climb/scripts/hc.py -h     # prints the nine subcommands
```

Requirements: `git` and Python 3.8 or newer. The helper uses the standard library only. Judge mode also needs
a way to start fresh-context model calls (subagents, or a headless CLI call) and whatever renders the
artifacts being judged (for web pages, a headless browser).

## Use it

When the user asks to hill-climb, optimize over rounds, or "keep improving X until...", read
`skills/hill-climb/SKILL.md` in full and follow it. In short:

1. Agree the score with the user in one sentence if they did not give one.
2. In the target repo: `hc.py setup --cmd '<score command>' --regex '<metric regex>' --direction min|max
   --gate '<test command>' --frozen <path>`, fill in `.hillclimb/HILLCLIMB.md`, then `hc.py baseline`.
3. Each round: make one change, then `hc.py round "<the change>"`. It commits, gates, measures, keeps or
   reverts, logs, and prints `NEXT` or `STOP`.
4. Keep going until it prints `STOP`. A big win is not a stop rule. Then report best vs baseline.

`examples/` holds two complete runs (a 370x speed-up scored by a benchmark, and a page polished by blind
judges) with their setup files and logs. Read one if you want to see what a finished run looks like.

## The benchmark

`bench/` measures whether the skill helps: four optimization tasks with hidden gates, agents run in isolated
`claude -p` sessions, scored from outside. Read `bench/README.md` before changing anything there. Raw runs in
`bench/runs/` are data; never edit them.

## Do not

- Change the score, gates or judge prompt after round 1 without logging a restart.
- Edit the benchmark, tests or judge prompt to make a number move.
- Push, publish or deploy as part of a run. The skill works on a local branch; shipping is the user's call.
