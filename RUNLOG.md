# RUNLOG

Lane: prove hill-climb works (2026-11-01). Newest entries last.

## 05:00 setup
- Benchmark lives in `bench/`. Three tasks with an objective score and gates the agent never sees:
  `logstats` (speed up a log analyzer; hidden edge-case tests plus a differential test against the original),
  `tinyclf` (raise a numpy classifier's accuracy; agent sees a 400-row validation split, scored on a hidden
  20k-row test split), `slowsuite` (speed up a pytest suite; hidden mutation check, 15 mutants the original kills).
- Arms: `plain` (task + "make it better"), `loop` (same + "iterate, do not stop early"), `hillclimb` (same as plain
  + "use the hill-climb skill", plugin loaded). Same model (sonnet), same $4 cap, same 40 min cap.
- Isolation verified by probe: `--setting-sources project`, CLAUDE.md excluded, strict empty MCP, fixed tool list.
  The agent sees no user skills, hooks or memory. Only the hillclimb arm gets `--plugin-dir`.
- Baselines (`bench/score.py --baselines`): logstats 2.279 s, tinyclf test acc 0.6251 (val 0.605), slowsuite 6.74 s, 15/15 mutants.
- Pilot (logstats, hillclimb, seed 0): 72 s, $0.09. One big rewrite to 0.0059 s, gates pass. Weakness: no baseline
  row logged, stopped after round 1 "because the gain was large", patience rule ignored.

## 05:10 main batch
- `python bench/batch.py --seeds 1-6 --jobs 3` (54 runs) started.
- Taste half: 100 Upworthy headline A/B pairs (same image and excerpt, CTR gap z >= 3), judged by the skill's blind
  3-judge protocol, panels of sonnet, opus and haiku (`bench/taste/judge.py`).
