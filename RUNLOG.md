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

## 05:28 main batch done (54 runs, 0 errors)
- Every arm on Sonnet is short: 4 to 13 turns, $0.06 to $0.11, 20 s to 2 min. "Loop, do not stop early" did not
  make the agent iterate; most runs are one big rewrite.
- hill-climb v1 failure modes seen in transcripts: stops after one big win ("the loop stopped because the gain
  was large"), skips the hc.py bookkeeping (empty or one-row results.tsv), sweeps hyperparameters on the val set.
- tinyclf (scored): test acc plain 0.806, loop 0.840, hillclimb v1 0.825. Val-to-test gap: plain 0.1 pts,
  loop 0.8, hillclimb v1 1.7. Claims match val exactly in every run (no misreporting).
- Taste (sonnet 100 pairs, opus 97): judges agree (kappa 0.71 and 0.83, panels match each other 84%) but pick
  the real CTR winner only 69% and 66%; a 3-judge majority is no better than a single judge.
- v2 skill drafted in bench/work/skill-v2 (one-command `hc.py round`, explicit "a big win is not a stop rule",
  eval-set overfitting section). v2 arm running: `batch.py --arms hillclimb-v2 --skill-dir bench/work/skill-v2`.

## 06:00 to 07:50 scoring under load, noisy task, skill v3
- Machine shared with other lanes (load average up to 115 on 12 cores). Wall-clock medians were useless
  (baseline samples 3.1 to 21.9 s). Scorer now times each run interleaved with the untouched baseline, uses
  in-process CPU time for logstats and the minimum paired wall time for slowsuite (sleeps only show in wall).
- Interim (Sonnet): no arm shipped a broken gate or an unbacked claim on logstats, tinyclf, slowsuite. On those
  tasks the skill does not beat a plain loop. The skill's core idea (noise discipline) was untested there.
- Added `noisytune`: tune 6 settings of a black-box simulated service, one bench run has ~8% noise, scored on
  the true noise-free p95 (baseline 190.8, optimum 103.9). Result: plain 124.8, loop 116.8, skill v1 146.3,
  skill v2 148.1. The skill did worse; 3 skill runs ended exactly at baseline.
- Root causes, both in hc.py: (1) stale Python bytecode. Agents chain `round` calls, so a revert and the next
  edit land in the same second with the same size; pyc is keyed on mtime seconds plus size, so round N measured
  round N-1's config. (2) The noise band was 2 x (MAD_best + MAD_cand), independent of the number of runs, so
  more runs could never resolve a gain; at 8% noise the band was 15 to 27%.
- v3 (tag skill-v3): band = 2 standard errors of the difference of medians (shrinks with sqrt(runs));
  `baseline` prints the band and a NOISY line with the runs needed; `round` clears untracked __pycache__ and
  waits out the second after a revert. Verified on a scratch copy: cache 1024 now WIN +27.6%, a 2% real gain
  reads NOISE at the measured band. v3 arm running on all four tasks.

## 08:02 handoff checkpoint
State: Sonnet arms plain/loop/hillclimb/hillclimb-v2 (3 tasks x 6) + noisytune (4 arms x 6) done; v3 arm
(4 tasks x 6) running into bench/runs/*-hillclimb-v3-*; Opus plain/loop/hillclimb-v2 x 3 tasks x 4 done (unscored).
Next, in order:
1. `python bench/score.py` (scores everything unscored; slowsuite is slow, ~4 min each under load).
2. `python bench/analyze.py --arms plain,loop,hillclimb,hillclimb-v2,hillclimb-v3 --out RESULTS` and
   `--model opus --arms plain,loop,hillclimb-v2 --out RESULTS-OPUS`. Writes paper/*_table.tex and assets/bench-*.png.
3. paper: write abstract/intro/results/fix/limits .tex (method, related, taste done), build with tectonic to
   paper/hill-climb.pdf, write paper/SUBMIT.md.
4. README leads with the measured result + figure; site/writeup.md, site/meta.json, site/launch-post.md.
5. gitleaks, push to origin main, pull into ~/code/hill-climb-skill (live skill symlink), fresh clone test,
   paste output here.

## 09:15 all runs scored; handoff to the write-up step
Totals: 192 agent runs (Sonnet: 5 arms x 4 tasks x 6 seeds = 120 minus v2/v1 not run on... see results.json;
Opus: 3 arms x 3 tasks x 4 seeds = 36), 900 judge calls. Tables: bench/RESULTS.md, bench/RESULTS-OPUS.md,
bench/taste/TASTE.md. LaTeX tables: paper/results_table.tex, paper/results-opus_table.tex, paper/taste_table.tex.
Figures: assets/bench-results-{light,dark}.png (Sonnet, 4 tasks), assets/bench-results-opus-{light,dark}.png.

Headline findings (all from the tables above):
1. Opus, test-suite task: without the skill, 5 of 8 runs (plain 3/4, loop 2/4) shipped a suite that lost a
   hidden mutant ("tagged truncated at scale"): they shrank the 400k-item fixture to 2k to 20k items and
   claimed the suite was no weaker. With skill v2: 0/4. Caveat: one mutant drives it; n=4 per arm.
2. Sonnet never broke a gate in any arm (0/120) and no unbacked claims except 1 (v2, noisytune). Claims
   matched outside measurement; agents are honest reporters at this level.
3. On the easy tasks the skill ties a plain loop: function speed ~400x all arms; tinyclf loop +21.5 pts,
   v1 +20.0, v2 +19.4, v3 +22.7 (best); suite 2.6x to 2.9x all. The skill costs about 2x the tokens.
4. noisytune (8% noise): plain 1.54x, loop 1.65x, v1 1.32x, v2 1.31x, v3 1.43x. The benchmark found two hc.py
   bugs (stale bytecode after fast reverts; noise band ignoring the run count). v3 fixed both (no run stuck at
   baseline) but still trails a free-form loop: v3 agents raised runs to 7 to 21, short of what NOISY asked,
   and tuned one knob per round where loop agents wrote averaged search scripts. Remaining gap, stated as such.
5. v2 made the agent iterate: logged rounds on logstats went from about 1 (v1, stopped after one big win) to
   6 to 11.
6. Taste: judges agree (kappa 0.45 haiku, 0.71 sonnet, 0.83 opus; panels match 70 to 84%) but pick the real
   A/B winner only 63 to 69% (majority 65 to 69%); majority of 3 is no better than one judge.
7. Validity notes: machine shared (load to 115), so speed scores use CPU time (logstats) and min paired wall
   time (slowsuite). Isolation covered config, not the filesystem: hill-climb agents located hc.py by path;
   one Opus loop run listed ~/.claude/skills (read no skill file). Transcripts sanitized by bench/sanitize.py.
