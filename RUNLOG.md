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
