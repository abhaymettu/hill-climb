# bench: does the skill help?

A controlled benchmark of coding agents improving code against a measure, with and without hill-climb.
Results and discussion: [`../paper/hill-climb.pdf`](../paper/hill-climb.pdf). Tables: [`RESULTS.md`](RESULTS.md),
[`RESULTS-OPUS.md`](RESULTS-OPUS.md), [`taste/TASTE.md`](taste/TASTE.md).

## Tasks

| Task | The agent is asked to | Score (from outside) | Hidden gate |
|---|---|---|---|
| `logstats` | speed up a log analyzer | CPU time of `analyze()`, paired with the baseline | edge-case tests and a differential test against the original |
| `tinyclf` | raise a numpy classifier's accuracy (sees a 400-row val split) | accuracy on a hidden 20,000-row test split | training under 20 s |
| `slowsuite` | speed up a pytest suite | suite wall time, paired with the baseline | 15 mutants of the library the original suite kills |
| `noisytune` | tune a black-box service's settings; one benchmark run varies by about 8% | the true, noise-free p95 | settings valid, memory budget |

Each task folder holds `workspace/` (what the agent gets), `hidden/` (what it never sees) and `task.json`.

## Arms

`plain` (the task), `loop` (the task plus "iterate, do not stop early"), `hillclimb` (the task plus "use the
hill-climb skill", skill v1 loaded as a plugin, tag `skill-v1`), `hillclimb-v2` (the same with the current skill).
Every run is a fresh, isolated `claude -p` session: no user settings, hooks, plugins, skills, memory, CLAUDE.md or
MCP servers; tools fixed to Bash, Read, Edit, Write, Glob, Grep, Skill; $4 and 40-minute caps.

## Reproduce

```sh
uv venv bench/.venv --python 3.12 && uv pip install --python bench/.venv/bin/python numpy pytest matplotlib
git worktree add bench/work/skill-v1 skill-v1                   # skill v1, for the hillclimb arm
python bench/batch.py --arms plain,loop --seeds 1-6              # 1 run = 1 isolated claude -p session
python bench/batch.py --arms hillclimb --seeds 1-6 --skill-dir bench/work/skill-v1
python bench/batch.py --arms hillclimb-v2 --seeds 1-6 --skill-dir .
python bench/score.py                                            # scores every run from outside
python bench/analyze.py --arms plain,loop,hillclimb,hillclimb-v2 # RESULTS.md, results.json, figures
python bench/taste/pairs.py && python bench/taste/judge.py --model sonnet && python bench/taste/analyze_taste.py
```

Agent runs are not deterministic, so a rerun gives new samples, not the same numbers. To re-score the committed
runs exactly, `python bench/score.py --rescore` rebuilds each run's final tree from `runs/<run>/final.diff`.

## Raw data

`runs/<task>-<arm>-s<seed>[-<model>]/` holds `meta.json` (prompt, cost, turns, wall time), `transcript.jsonl.gz`
(the full stream-json session), `final.diff` (what the agent left, against the task), `claim.json` (what it said
it achieved), `hillclimb-results.tsv` (the skill's own log, when there is one) and `score.json`.
