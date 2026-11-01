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

`plain` (the task), `loop` (the task plus "iterate, do not stop early"), and the skill arms: the task plus "use
the hill-climb skill", with one version of the skill loaded as a plugin. `hillclimb` is skill v1 (tag `skill-v1`),
`hillclimb-v2` is tag `skill-v2` (the arm ran it without the judge-panel notes in `references/judging.md`, which
scalar tasks never read), `hillclimb-v3` is tag `skill-v3`. Every run is a fresh, isolated `claude -p` session: no
user settings, hooks, plugins, skills, memory, CLAUDE.md or MCP servers; tools fixed to Bash, Read, Edit, Write,
Glob, Grep, Skill; $4 and 40-minute caps. Isolation covers configuration, not the filesystem.

Committed runs: 120 on Sonnet (5 arms x 4 tasks x 6 seeds) and 36 on Opus (`plain`, `loop`, `hillclimb-v2` x the
first three tasks x 4 seeds). `logstats-hillclimb-s0` is the harness pilot and is left out of every table.

## Reproduce

```sh
uv venv bench/.venv --python 3.12 && uv pip install --python bench/.venv/bin/python numpy pytest matplotlib
for v in 1 2 3; do git worktree add bench/work/skill-v$v skill-v$v; done
T=logstats,tinyclf,slowsuite,noisytune
python bench/batch.py --tasks $T --arms plain,loop --seeds 1-6          # 1 run = 1 isolated claude -p session
python bench/batch.py --tasks $T --arms hillclimb --seeds 1-6 --skill-dir bench/work/skill-v1
python bench/batch.py --tasks $T --arms hillclimb-v2 --seeds 1-6 --skill-dir bench/work/skill-v2
python bench/batch.py --tasks $T --arms hillclimb-v3 --seeds 1-6 --skill-dir bench/work/skill-v3
python bench/batch.py --model opus --arms plain,loop --seeds 1-4
python bench/batch.py --model opus --arms hillclimb-v2 --seeds 1-4 --skill-dir bench/work/skill-v2
python bench/score.py                                                   # scores every unscored run from outside
python bench/analyze.py --arms plain,loop,hillclimb,hillclimb-v2,hillclimb-v3 --out RESULTS
python bench/analyze.py --model opus --arms plain,loop,hillclimb-v2 --out RESULTS-OPUS
python bench/taste/pairs.py
for m in haiku sonnet opus; do python bench/taste/judge.py --model $m; done
python bench/taste/analyze_taste.py
```

Agent runs are not deterministic, so a rerun gives new samples, not the same numbers. To re-score the committed
runs, `python bench/score.py --rescore [run ...]` rebuilds each run's final tree from `runs/<run>/final.diff`
(speed scores are timings, so they move a little from machine to machine; gate results should not).

## Raw data

`runs/<task>-<arm>-s<seed>[-<model>]/` holds `meta.json` (prompt, cost, turns, wall time), `transcript.jsonl.gz`
(the full stream-json session), `final.diff` (what the agent left, against the task), `claim.json` (what it said
it achieved), `hillclimb-results.tsv` (the skill's own log, when there is one) and `score.json`.
