---
name: hill-climb
description: Disciplined improve-measure-keep-or-revert loop for any kind of work. Use whenever the user says "hill-climb this", "keep improving X until...", "optimize", "make it faster/smaller/better and prove it", "run experiments overnight", "autoresearch", or wants something improved over many rounds with evidence. Works for code speed, bundle size, test time, model loss, latency, benchmark scores (a number from a command) and equally for taste work such as UI look, copy or design (blind pairwise judges), with hard gates like tests and contrast that veto any round. Use it even when the user does not say "hill-climb" but asks for iterative improvement against a measure.
---

# Hill climb

Make one change, score it against the current best, keep it if it wins, revert it if not, log it, repeat.
The loop is simple. Runs fail in the details: a score that shifts mid-run, a noisy number read as a win,
a judge who knows which version is new, a run that never stops. This skill is those details.

`scripts/hc.py` (Python 3, standard library) does the mechanical parts: `init`, `measure`, `compare`,
`flip`, `log`, `status`. Run `python3 <skill-dir>/scripts/hc.py -h`.

## 1. Pick the score mode

| Mode | When | Decides a round |
|---|---|---|
| **scalar** | A command prints or implies one number: wall time, bundle bytes, loss, p95 latency, a benchmark score | `hc.py compare` on repeated measurements |
| **judge** | Quality is a matter of taste: a page's look, an image, copy, an API's feel | blind pairwise vote of fresh-context judges, see `references/judging.md` |
| **composite** | Either of the above plus gates | gates first, then the score |

Gates are pass/fail checks that veto a round whatever the score says: tests pass, it builds, contrast
holds, memory stays under a cap, no guard metric regresses. Nearly every real run is composite. A faster
function that breaks a test is a loss.

If the user gives no measure, propose one in a sentence and get a yes before starting. A climb toward
the wrong number is worse than no climb.

### Ports and rewrites: parity first, then speed

When the target is a re-implementation of something that already exists (a port to another language, a
clone of a tool, a replacement library), the existing thing is the score. Run it as two climbs:

1. **Parity.** Pin the reference's exact version. Build a corpus of real inputs, then copy some of them
   with faults injected (a syntax error, a missing file, a bad type) so error paths and messages are
   compared too, not just the happy path. Record the reference's outputs once and freeze them. Score:
   the count of cases whose output matches byte for byte (scalar, `--direction max`, `--min-delta 0`).
   Stop at all cases matching.
2. **Speed (or size).** Restart with parity as a gate: every case still matches. Score the timing against
   a stated target ("2x faster than the reference") and stop when it is reached.

Never loosen the comparison to make a case pass; normalizing a field that is legitimately different
(a timestamp, an absolute path) is a setup decision made before round 0 and written in HILLCLIMB.md.

## 2. Setup, written before round 1

1. Work on a new branch, `hill-climb/<tag>` (if the name is taken by an earlier run, add `-2`), with no uncommitted changes to tracked files (untracked build
   output such as `__pycache__/` is fine). If the target is not in git, `git init` it. Uncommitted user work
   must never be at risk from a revert: commit it on its own branch, stash it, or stop and ask.
2. `hc.py init` creates `.hillclimb/HILLCLIMB.md` (from `references/setup-template.md`), `.hillclimb/results.tsv`
   and `.hillclimb/rounds/`, and adds `.hillclimb/` to `.git/info/exclude` so the log survives every revert.
3. Fill in HILLCLIMB.md: the target and its editable surface, what is frozen (tests, eval harness, the
   benchmark itself), the score, the exact gate commands, the budget, the stop rule. For judge mode, also
   write the judge prompt to `.hillclimb/judge-prompt.md`; it is frozen like the rest. Show it to the user if they are
   around; do not wait on them if they are not.
4. A quick probe before round 0 (one run, to see how long it takes or whether the metric parses) is fine
   and is not logged. Round 0: measure the untouched baseline exactly as every later round will be measured, and log it with
   `verdict=baseline`. For judge mode, capture the baseline artifacts.

**The score never changes mid-run.** Not the command, the regex, the rubric, the views, the judge count
or the gates. If it must change, that is a restart: note why under Restarts in HILLCLIMB.md and
re-measure round 0. Otherwise, a round-7 "win" was measured with a different ruler from round 3's.

Freezing the evaluation is equally important. Editing the test, the benchmark input or the judge prompt
to make a number move is not a win; it is a different run. That is why HILLCLIMB.md lists what is frozen.

## 3. One round

1. **Pick one idea.** One change per round, so a result can be attributed. Prefer ideas the last loss's
   evidence points to. Deletions that hold the score are wins too: simpler at equal quality is better.
2. **Make it and commit it**: `git commit -am "r07: <the change>"`.
3. **Gates.** Run them. Any failure is a loss; skip the score. A trivial slip (a typo, a missing import)
   gets one fix and re-run; a broken idea gets reverted, not nursed. A guard on the benchmark's own output
   (a checksum line, a result count) can ride along with the measurement: `measure --expect-line '<exact line>'`
   (taken literally) or `--expect '<regex>'` fails any run whose output lacks it, and the round's JSON records
   which guards ran.
4. **Score.**
   - scalar: `hc.py measure --runs 5 --regex 'seconds=([0-9.]+)' --out .hillclimb/rounds/r07.json -- <cmd>`,
     then `hc.py compare .hillclimb/rounds/best.json .hillclimb/rounds/r07.json --direction min --min-delta 0.02`.
     Without `--regex`, the metric is the command's whole wall time, startup and setup included; use that only
     when the whole command is what you are speeding up.
   - judge: capture, then `hc.py flip --judges 3 --best <best dir> --cand <cand dir> --out .hillclimb/rounds/r07/blind`,
     which records the coin flips and gives each judge copies under neutral names (a path like `r07/` would
     tell the judge which side is new). Run the judges, unblind, majority. Details in `references/judging.md`.
5. **Decide.** WIN keeps. LOSS reverts. NOISE reverts too, with one exception: a change that deletes more
   code than it adds and passes the gates is kept at equal score (`notes=simpler`). Simpler at equal
   quality is a real gain the metric cannot see.
6. **Log every round, losses included, before reverting**, so the row records the candidate's commit:
   `hc.py log .hillclimb/results.tsv round=7 change="memoize parse" score=0.412 gates=pass verdict=keep notes="gain 9%, bar 2%"`.
   `score` is the median for scalar runs, the vote (`2/3 cand`) for judge runs. Then act: on a keep, the
   candidate becomes the best (scalar: copy its JSON to `best.json`); on a revert, `git reset --hard HEAD~1`.
   The log is the run's memory; a silent loop looks the same as a stuck one.
7. **Check stop**: `hc.py status .hillclimb/results.tsv --patience 5 --budget 20`.

Redirect long command output to a file and read only the metric and the tail on failure. Each round's
full output in your context fills it in a dozen rounds.

## 4. Noise

A scalar is a sample, not a fact. Treat a single run as a rumor.

- `measure` takes 5 runs after 1 warmup by default and reports the median and MAD (median absolute
  deviation). `compare` needs the gain to clear the larger of `--min-delta` and twice the pooled noise.
  Anything inside the band is NOISE and reverts.
- Pick `--min-delta` for what matters to the user, not what the instrument can see: 2% for timings, 0 for
  deterministic counts like bytes or test failures.
- Mind the instrument's resolution. A metric printed to 4 decimals that reaches 0.007 moves in steps of
  about 1.5%, and its MAD can read 0. Decide at setup how small the number can get, and set `--min-delta`
  to at least 2 or 3 steps at that size. If it bites mid-run anyway, widening the bar or making the
  benchmark do more work is a change to the score, so it is a restart.
- On a WIN that is close to the bar, re-measure the best and the candidate back to back and compare again.
  Machines drift (thermals, other jobs, caches) and the best's numbers may be stale.
- A gain that only appears at `--runs 1` is not a gain.

## 5. Stop rules

Stop at the first of: the round budget or time budget, `patience` rounds in a row without a win, the
target value reached, or the user says stop. Without a stop rule, the run spends hours on noise-level
tweaks once real gains run out.

Defaults if the user named none: 20 rounds, patience 5.

## 6. Escaping a local peak

Small safe changes plateau. When half the patience, rounded up, is spent without a win (3 losses in a
row at the default patience of 5, 2 at patience 3), spend the next round on one **larger move**: a
different algorithm, a restructured layout, a different approach to the whole thing rather than a tweak.
It is still one idea, judged under the same score and gates, kept only if it wins. Mark it `notes=big-move`.

At most one big move per plateau. If it loses, return to small moves from the best; after `patience`
losses in a row the run stops. With a patience of 2 or less there is no room for a big move; say so in the
setup rather than skipping it silently. Never restart from the baseline unless the log shows the climb went sideways
(see the drift check in `references/judging.md`).

## 7. Parallel candidates (optional)

When rounds are slow and ideas are independent, try 2 or 3 candidates per round in separate git worktrees
(or subagents, each on its own branch). Score each against the same best and keep only the single best
winner. Then the next round starts from it. Keep it bounded: never more than 3 at once, and never run
heavy jobs (builds, benchmarks, renders) in parallel with each other when the score is a timing, since
they distort each other's numbers.

## 8. Long runs and handoff

- One heavy job at a time by default.
- Watch round wall time in the log. If the gates and the measurement take far longer than the change, the
  climb is gate-bound: stop, speed up the gates as their own run (same checks, same verdicts on the same
  inputs; caching or a prebuilt snapshot, never fewer cases), then restart this run on the faster gates.
- If a turn has to end while something is still running, first write `.hillclimb/NEXT.md`: what is
  running, how to check it, what wakes the next step, and the next idea in the queue. Never leave background
  work without that note.
- Anyone resuming reads HILLCLIMB.md, the last rows of results.tsv and NEXT.md, and carries on from the
  best commit.

## 9. Report

End with:

```
Hill climb: <target>
Score: <metric, direction or judge rubric>  |  Gates: <list>
Baseline <value>  ->  Best <value>  (<change>, round <n>)
Rounds <n>: <wins> kept, <losses> reverted, <gate fails> vetoed   |   Stop: <which rule>
Wins, in order: r03 <change> (<delta>), ...
Best losses worth a second look: ...
Log: .hillclimb/results.tsv   Branch: hill-climb/<tag>
```

For judge runs, include the final best-vs-baseline panel result. A number that never moved is a finding:
report it, do not hide it.

## Red flags

- The score, rubric or views changed after round 1 without a restart.
- A test, benchmark input or judge prompt was edited during the run.
- A WIN from a single measurement, or with a gain inside the noise band.
- The judge knew which side was new, or the builder judged its own change.
- Two ideas in one round.
- A round missing from the log because it lost.
- Background work left running with no NEXT.md.
