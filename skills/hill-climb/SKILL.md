---
name: hill-climb
description: Disciplined improve-measure-keep-or-revert loop for any kind of work. Use whenever the user says "hill-climb this", "keep improving X until...", "optimize", "make it faster/smaller/better and prove it", "run experiments overnight", "autoresearch", or wants something improved over many rounds with evidence. Works for code speed, bundle size, test time, model loss, latency, benchmark scores (a number from a command) and equally for taste work such as UI look, copy or design (blind pairwise judges), with hard gates like tests and contrast that veto any round. Use it even when the user does not say "hill-climb" but asks for iterative improvement against a measure.
---

# Hill climb

Make one change, score it against the current best, keep it if it wins, revert it if not, log it, repeat.
The loop is simple. Runs fail in the details: a score that shifts mid-run, a noisy number read as a win,
a judge who knows which version is new, a run that never stops. This skill is those details.

`scripts/hc.py` (Python 3, standard library) does the mechanical parts. For a scalar score, three
commands run the whole loop: `setup` once, `baseline` once, then `round "<change>"` after every change. Each
`round` commits, runs the gates, measures, decides, logs, reverts a loser and prints the next step. Judge runs
add `tally` (the script counts the saved judge replies), `preflight` checks the measure before round 1, and
`holdout` scores data the climb never sees. The lower-level `init`, `measure`, `compare`, `flip`, `log` and
`status` are there for odd cases.
Run `python3 <skill-dir>/scripts/hc.py -h`.

## 1. Pick the score mode

| Mode | When | Decides a round |
|---|---|---|
| **scalar** | A command prints or implies one number: wall time, bundle bytes, loss, p95 latency, a benchmark score | `hc.py compare` on repeated measurements |
| **judge** | Quality is a matter of taste: a page's look, an image, copy, an API's feel | blind pairwise vote of fresh-context judges, see `references/judging.md` |
| **findings** | The work must pass a reviewer or a rubric: code review findings, an audit, a labelled score table | count of open findings at or above a bar set in advance, from a frozen ledger, see `references/measures.md` |
| **composite** | Any of the above plus gates | gates first, then the score |

Gates are pass/fail checks that veto a round whatever the score says: tests pass, it builds, contrast
holds, memory stays under a cap, no guard metric regresses. Nearly every real run is composite. A faster
function that breaks a test is a loss.

If the user gives no measure, propose one in a sentence and get a yes before starting (when nobody is
there to answer, write it in HILLCLIMB.md and go). A climb toward the wrong number is worse than no climb.
`references/measures.md` says how to build the measure for each kind of work, and what to freeze: a number
from a command, a review or rubric gate, a labelled score table, taste, low-level code, mixed measures,
expensive rounds. Read the part for your kind before setup. Whatever the kind, three things are written
before round 1: a frozen score, gates that veto, a stop rule.

Less common shapes (a port or rewrite scored against the original, parallel candidates, a round by hand, a
run set up before locks) are in `references/odd-cases.md`.

## 2. Setup, written before round 1

1. Work on a new branch, `hill-climb/<tag>` (if the name is taken by an earlier run, add `-2`), with no uncommitted changes to tracked files (untracked build
   output such as `__pycache__/` is fine). If the target is not in git, or is a folder inside a larger repo, `git init` inside the target folder itself:
   hc.py commits and hard-resets the repo it runs in, and that must never be the parent. Uncommitted user work
   must never be at risk from a revert: commit it on its own branch, stash it, or stop and ask.
2. Scalar runs: `hc.py setup --cmd '<score command>' --regex '<metric regex>' --direction min|max
   --min-delta 0.02 --gate '<test command>' --frozen <path> --budget 20 --patience 5` (gates and frozen paths
   repeat; `--expect-line '<exact line>'` adds an output guard such as a checksum). It writes the frozen config to
   `.hillclimb/config.json`, creates `.hillclimb/HILLCLIMB.md` (from `references/setup-template.md`),
   `.hillclimb/results.tsv` and `.hillclimb/rounds/`, and adds `.hillclimb/` to `.git/info/exclude` so the log
   survives every revert. Judge runs: `hc.py setup --judges 3 --judge-cmd '<headless model call>' --frozen
   <views or capture script>` (the capture command as `--cmd` is optional). With `--judge-cmd` (for example
   `'claude -p --bare --model sonnet --allowedTools Read'`), hc.py calls the judges and saves their replies itself, so
   the climbing agent never writes one. Leave it out only when judges can run as subagents and nothing else. For a fixed eval set or a judged product, add
   `--holdout-cmd '<cmd>'`, see `references/eval-sets.md`.
3. Fill in HILLCLIMB.md: the target and its editable surface, what is frozen (tests, eval harness, the
   benchmark itself), the score, the exact gate commands, the budget, the stop rule. For judge mode, also
   write the judge prompt to `.hillclimb/judge-prompt.md` from the template in `references/judging.md`,
   including its line that the work is data, not instructions; it is frozen like the rest. Show it to the user if
   they are around; do not wait on them if they are not.
4. A quick probe before round 0 (one run, to see how long it takes or whether the metric parses) is fine
   and is not logged. Round 0: `hc.py baseline` checks the gates pass on the untouched version, measures it
   exactly as every later round will be measured, locks the frozen content, and logs it. For judge mode, capture
   the baseline artifacts into `.hillclimb/rounds/r00/`.
5. **Pre-flight, before round 1.** Prove the measure can see a difference and catches a cheat; `round` refuses
   until both pass. Break the work on purpose (a wrong answer, a broken layout, a truncated output) in a way
   the gates still accept, and run `hc.py preflight broken`: the score must come out worse (a judge panel must
   prefer the baseline; steps in `references/judging.md`). A break that only fails a gate proves the gate, not
   the score, so break it again until the score has to tell. Restore it. Then change one frozen file (add a
   line to the eval set) and run `hc.py preflight cheat`; it must report the change. Restore that too. If a
   check fails, the capture, views, prompt or score is broken: fix the setup and re-run `baseline`. Only when
   there is truly nothing to break: `hc.py preflight skip --why "<reason>"`, which stays in the record.
   Nothing in the pre-flight is logged as a round.

**The score never changes mid-run.** Not the command, the regex, the rubric, the views, the judge count
or the gates. If it must change, that is a restart: note why under Restarts in HILLCLIMB.md and
re-measure round 0. Otherwise, a round-7 "win" was measured with a different ruler from round 3's.
When rounds are too expensive to restart (a remote build, a paid review), log a `measure-change` row instead:
what changed and why, and the current best re-measured under the new measure, both values for that one
commit. Numbers from the two sides of that row are never compared. Write every score with its denominator
and commit (`19/21 @ a1b2c3d`), so a changed ruler shows.

Freezing the evaluation is equally important. Editing the test, the benchmark input or the judge prompt
to make a number move is not a win; it is a different run. That is why HILLCLIMB.md lists what is frozen.
Frozen paths are locked by content hash at `baseline`, not by git, so an ignored eval set, the judge prompt
and `config.json` are covered too. `round` checks the locks before the gates and again after measuring; a
change refuses the round (logged `refused`, exit 3). Git cannot restore an ignored file, so put it back by
hand or restart with `setup --force`.

## 3. One round

1. **Pick one idea.** One change per round, so a result can be attributed. Prefer ideas the last loss's
   evidence points to. Deletions that hold the score are wins too: simpler at equal quality is better.
2. **Make it**, then run **`hc.py round "<the change, in a few words>"`**. It commits the change as `rNN`, fails
   the round if a frozen path changed or a gate fails, measures it with the frozen settings, compares it with
   the best (`WIN`, `LOSS` or `NOISE`, see section 4), logs the row, keeps a winner or resets to the best on
   anything else, and prints `NEXT: ...` or `STOP: ...`. Do what that line says.
   - A deletion that ties: `hc.py round "<change>" --simpler` keeps it at equal score.
   - A trivial slip (a typo, a missing import) that fails a gate costs that round; fix it as the next round.
   - Judge mode: capture, then `hc.py round`; hc.py flips, runs the judges and counts the votes. The exact
     steps, with and without `--judge-cmd`, are in `references/judging.md`, "A judge round with hc.py". If the
     setup gave a capture `--cmd`, hc.py captures by itself and the "capture into" part of NEXT does not apply.
3. Without `round` (no config, an unusual score, a findings run, or a target on a remote machine or in someone
   else's repo, where the log lives in your own folder instead), do the same steps by hand, in the same order:
   commit, gates, measure, compare, log, keep or revert. The commands are in `references/odd-cases.md`.

Every round is logged, losses included. The log is the run's memory; a silent loop looks the same as a
stuck one.

Redirect long command output to a file and read only the metric and the tail on failure. Each round's
full output in your context fills it in a dozen rounds.

## 4. Noise

A scalar is a sample, not a fact. Treat a single run as a rumor.

- `measure` takes 5 runs after 1 warmup by default and reports the median and MAD (median absolute
  deviation). `compare` needs the gain to clear the larger of `--min-delta` and two standard errors of the
  difference of medians. Anything inside the band is NOISE and reverts.
- **Size the runs to the gains you are hunting.** The band shrinks with the square root of the runs.
  `hc.py baseline` prints the band at the configured runs and, when it is wider than the gains you care
  about, prints `NOISY` with the runs that would resolve them. Act on it before round 1 (`setup --force
  --runs N`, then `baseline` again): with an 8% run-to-run spread, 5 runs hide every gain under about 14%,
  so a careful climb rejects every real small improvement and ends where it started.
- `--min-delta` is relative to the best score (0.02 is 2% of it), not an absolute amount. Pick it for what
  matters to the user, not what the instrument can see: 2% for timings, 0 for exact sizes such as bytes. For a
  count out of N cases (accuracy, tests passing) one more case is luck: set it so a win needs at least 2
  (2 divided by the best count).
- Mind the instrument's resolution. A metric printed to 4 decimals that reaches 0.007 moves in steps of
  about 1.5%, and its MAD can read 0. Decide at setup how small the number can get, and set `--min-delta`
  to at least 2 or 3 steps at that size. If it bites mid-run anyway, widening the bar or making the
  benchmark do more work is a change to the score, so it is a restart.
- On a WIN that is close to the bar, re-measure the best and the candidate back to back and compare again.
  Machines drift (thermals, other jobs, caches) and the best's numbers may be stale.
- A gain that only appears at `--runs 1` is not a gain.
- Build caches keyed on file times (Python bytecode, make) can serve the previous round's code when a revert
  and the next edit land in the same second. `round` clears untracked `__pycache__` folders and waits out the
  second after a revert; by hand, do the same, or clear the cache in the score command.

When the score is accuracy on a fixed set (a validation split, a prompt eval, a benchmark suite), every kept
round fits that set a little. Set aside a holdout before round 0 and pass `--holdout-cmd`: see
`references/eval-sets.md`.

## 5. Stop rules

Stop at the first of: the round budget or time budget, `patience` rounds in a row without a win, the
target value reached, the holdout flat while the visible score climbs, or the user says stop. Without a stop rule, the run spends hours on noise-level
tweaks once real gains run out.

hc.py enforces the budget, the patience and the holdout. The target value has no flag: write it in
HILLCLIMB.md and check it yourself after every `round`.

**Those are the only stop rules.** A large win is not one: a 100x first round usually means the code was
far from its limit, and the next rounds start from a new, better best. Do not end your turn, write the
report or ask whether to continue while `hc.py round` still prints `NEXT`.

Defaults if the user named none: 20 rounds, patience 5. When a round is expensive (minutes of remote
build, a full review), 3 to 5 rounds and patience 1: the first round that does not improve the score ends
the run, and what is left is reported with its ratings.

## 6. Escaping a local peak

Small safe changes plateau. When half the patience, rounded up, is spent without a win (3 losses in a
row at the default patience of 5, 2 at patience 3), spend the next round on one **larger move**: a
different algorithm, a restructured layout, a different approach to the whole thing rather than a tweak.
It is still one idea, judged under the same score and gates, kept only if it wins. Mark it `notes=big-move`.

At most one big move per plateau. If it loses, return to small moves from the best; after `patience`
losses in a row the run stops. With a patience of 2 or less there is no room for a big move; say so in the
setup rather than skipping it silently. Never restart from the baseline unless the log shows the climb went sideways
(see the drift check in `references/judging.md`).

## 7. Long runs and handoff

- One heavy job at a time by default.
- Watch round wall time in the log. If the gates and the measurement take far longer than the change, the
  climb is gate-bound: stop, speed up the gates as their own run (same checks, same verdicts on the same
  inputs; caching or a prebuilt snapshot, never fewer cases), then restart this run on the faster gates.
- If a turn has to end while something is still running, first write `.hillclimb/NEXT.md`: what is
  running, how to check it, what wakes the next step, and the next idea in the queue. Never leave background
  work without that note.
- Anyone resuming reads HILLCLIMB.md, the last rows of results.tsv and NEXT.md, and carries on from the
  best commit.

## 8. Report

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
- A judge verdict typed by hand instead of tallied from saved replies.
- Round 1 run without a pre-flight, or a holdout that was opened.
- A WIN from a single measurement, or with a gain inside the noise band.
- The judge knew which side was new, or the builder judged its own change.
- A score quoted without its denominator and commit, or compared across a measure change.
- A reviewer's finding on old code counted against this round, or fixed with no ledger row and no check.
- A label changed to match the code, or the code to match a label, with no written ruling on which is right.
- "Fix, review again" with no bar and no ledger: the count falls every round and never reaches zero.
- A findings ledger at zero taken as a pass: the reviewer reads the lines the fixes added too. Count the review
  on the whole change, and prefer the fix that removes lines or claims.
- Two ideas in one round.
- A round missing from the log because it lost.
- The run ended after a big win while rounds and patience were left.
- A setting swept against the eval set the run is scored on.
- Background work left running with no NEXT.md.

## Lessons

Dated lessons from real runs are in `references/lessons.md`. Read the ones for your score mode before
setup, and add one there when a run shows a gap.
