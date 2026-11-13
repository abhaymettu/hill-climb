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
2. Scalar runs: `hc.py setup --cmd '<score command>' --regex '<metric regex>' --direction min|max
   --min-delta 0.02 --gate '<test command>' --frozen <path> --budget 20 --patience 5` (gates and frozen paths
   repeat; `--expect-line '<exact line>'` adds an output guard such as a checksum). It writes the frozen config to
   `.hillclimb/config.json`, creates `.hillclimb/HILLCLIMB.md` (from `references/setup-template.md`),
   `.hillclimb/results.tsv` and `.hillclimb/rounds/`, and adds `.hillclimb/` to `.git/info/exclude` so the log
   survives every revert. Judge runs: `hc.py setup --judges 3 --judge-cmd '<headless model call>' --frozen
   <views or capture script>` (the capture command as `--cmd` is optional). With `--judge-cmd` (for example
   `'claude -p --model sonnet --allowedTools Read'`), hc.py calls the judges and saves their replies itself, so
   the climbing agent never writes one. Leave it out only when judges can run as subagents and nothing else. For a fixed eval set or a judged product, add
   `--holdout-cmd '<cmd>'`, see "Climbing on a fixed eval set".
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
   until both pass. Break the work on purpose (a wrong answer, a broken layout, a truncated output) and run
   `hc.py preflight broken`: a scalar run must score worse or fail a gate; a judge run must have the panel
   prefer the baseline (capture the broken version into `.hillclimb/rounds/preflight/cand/`; with
   `--judge-cmd`, `preflight broken` flips and judges it itself; without it, `flip` it against `r00` into
   `rounds/preflight/blind`, judge, `tally`, then `preflight broken --panel <panel.json>`). Restore
   it. Then change one frozen file (add a line to the eval set) and run `hc.py preflight cheat`; it must
   report the change. Restore that too. If a check fails, the capture, views, prompt or score is broken: fix
   the setup and re-run `baseline`. Only when there is truly nothing to break: `hc.py preflight skip --why
   "<reason>"`, which stays in the record. Nothing in the pre-flight is logged as a round.

**The score never changes mid-run.** Not the command, the regex, the rubric, the views, the judge count
or the gates. If it must change, that is a restart: note why under Restarts in HILLCLIMB.md and
re-measure round 0. Otherwise, a round-7 "win" was measured with a different ruler from round 3's.

Freezing the evaluation is equally important. Editing the test, the benchmark input or the judge prompt
to make a number move is not a win; it is a different run. That is why HILLCLIMB.md lists what is frozen.
Frozen paths are locked by content hash at `baseline`, not by git, so an ignored eval set, the judge prompt
and `config.json` are covered too. `round` checks the locks before the gates and again after measuring; a
change refuses the round (logged `refused`, exit 3). Git cannot restore an ignored file, so put it back by
hand or restart with `setup --force`.

A run set up before locks existed has none: hc.py prints one `legacy run` line and keeps the old checks
(and `--verdict`). Let them finish; start new runs with `setup`.

## 3. One round

1. **Pick one idea.** One change per round, so a result can be attributed. Prefer ideas the last loss's
   evidence points to. Deletions that hold the score are wins too: simpler at equal quality is better.
2. **Make it**, then run **`hc.py round "<the change, in a few words>"`**. It commits the change as `rNN`, fails
   the round if a frozen path changed or a gate fails, measures it with the frozen settings, compares it with
   the best (`WIN`, `LOSS` or `NOISE`, see section 4), logs the row, keeps a winner or resets to the best on
   anything else, and prints `NEXT: ...` or `STOP: ...`. Do what that line says.
   - A deletion that ties: `hc.py round "<change>" --simpler` keeps it at equal score.
   - A trivial slip (a typo, a missing import) that fails a gate costs that round; fix it as the next round.
   - Judge mode with `--judge-cmd`: capture into the folder the NEXT line names, then `hc.py round
     "<change>"`. If the setup gave a capture `--cmd`, skip the capture: hc.py runs `<cmd> <folder>` itself
     at baseline and every round, and refuses a round folder someone else made. The candidate must show the
     same views (file names) as the best, and the best's captures are locked by hash once kept. After the
     gates pass, hc.py flips the candidate against the best's captures, runs the judge
     command once per judge (the frozen prompt on stdin, the judge's blind folder as cwd and `$HC_JUDGE_DIR`),
     saves each stdout unedited as `blind/judge-N.txt` with a receipt in `blind/judges.json`, and counts the
     votes. `--panel` and `--verdict` are refused, and so is a round whose `blind/` folder already exists: a
     reply hc.py did not write is a planted one. If a judge fails (a crash, a timeout, no `VERDICT:` line),
     nothing is logged, the commit is undone with the change left in the tree, and the replies are set aside
     as `blind.failed-N` (the log row of the round that finally runs says `attempt N`); run the same round
     again. No reply reaches the disk until every judge has answered.
   - Judge mode without `--judge-cmd`: run the panel first (capture into the folder the NEXT line names, `flip`,
     judges, save each reply as `blind/judge-N.txt`, `hc.py tally <blind dir>`, see `references/judging.md`), then
     `hc.py round "<change>" --panel .hillclimb/rounds/rNN/blind/panel.json`. The script counts the votes; a
     typed `--verdict` is refused, and so is a panel flipped for another round or a reply edited after the
     tally (nothing is committed, so fix it and run the same round again). The script can check that the
     record is consistent, not who wrote a reply: replies come only from fresh-context judges, saved unedited.
3. Without `round` (no config, an unusual score), do the same steps by hand, in this order: commit
   (`git commit -am "r07: <change>"`); run the gates, any failure is a loss; `hc.py measure --runs 5 --regex
   '<re>' --out .hillclimb/rounds/r07.json -- <cmd>`; `hc.py compare .hillclimb/rounds/best.json
   .hillclimb/rounds/r07.json --direction min --min-delta 0.02`; `hc.py log .hillclimb/results.tsv round=7
   change="..." score=<median> gates=pass verdict=keep|revert notes="..."` before reverting, so the row holds
   the candidate's commit; on a keep copy the JSON to `best.json`, otherwise `git reset --hard HEAD~1`;
   `hc.py status .hillclimb/results.tsv --patience 5 --budget 20`.

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
- Pick `--min-delta` for what matters to the user, not what the instrument can see: 2% for timings, 0 for
  deterministic counts like bytes or test failures.
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

### Climbing on a fixed eval set

When the score is accuracy on a fixed set (a validation split, a prompt eval, a benchmark suite), every
kept round fits that set a little. Twenty rounds of small wins on 400 examples can be pure fit.

- Choose settings (hyperparameters, thresholds, prompt wording variants) inside the training data, with
  cross-validation, and let the eval set only decide the round. Never sweep a setting against the eval set.
- Prefer larger, principled changes over tuning a number to the third decimal.
- Before round 0, set aside about 20% of the real set as a holdout, add its path to `--frozen`, and pass
  `--holdout-cmd '<the score command on the holdout>'`. Never open those files again. hc.py runs it at
  baseline, after every 5th win and at the end. If the visible score climbed and the holdout did not, it
  prints `STOP: overfitting`: stop and report both numbers. Judge runs: the holdout command captures held-out
  views; hc.py flips best against baseline on them and, with `--judge-cmd`, judges them on the spot;
  without it, it waits for a panel (`hc.py holdout --panel`).
- In the report, call the final number what it is: the score on the set you climbed on, which overstates
  performance on new data, and give the holdout number beside it.

## 5. Stop rules

Stop at the first of: the round budget or time budget, `patience` rounds in a row without a win, the
target value reached, the holdout flat while the visible score climbs, or the user says stop. Without a stop rule, the run spends hours on noise-level
tweaks once real gains run out.

**Those are the only stop rules.** A large win is not one: a 100x first round usually means the code was
far from its limit, and the next rounds start from a new, better best. Do not end your turn, write the
report or ask whether to continue while `hc.py round` still prints `NEXT`.

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
- A judge verdict typed by hand instead of tallied from saved replies.
- Round 1 run without a pre-flight, or a holdout that was opened.
- A WIN from a single measurement, or with a gain inside the noise band.
- The judge knew which side was new, or the builder judged its own change.
- Two ideas in one round.
- A round missing from the log because it lost.
- The run ended after a big win while rounds and patience were left.
- A setting swept against the eval set the run is scored on.
- Background work left running with no NEXT.md.

## Lessons

- 2026-11-12: three holes, each proven on a test repo. A frozen eval set that git ignores grew from 3 to 6
  lines mid-run and the round was kept as a WIN, because the freeze check was a `git diff`. An edit to
  `.hillclimb/judge-prompt.md` passed for the same reason. `round --verdict WIN` kept a round with no judge
  reply on disk. Fix: lock by content hash, let the script tally the panel, and test each hole before and
  after (`tests/test_hc.py`). Any check built on git sees only what git tracks.
- 2026-11-12: a climb on a fixed set needs a holdout the script runs, not advice to keep one; and a panel that
  cannot see the views votes TIE every round, so prove the measure separates a broken version before round 1.
- 2026-11-12, from the review: check what you can before the commit. A panel checked after `round` committed
  reset an honest round's work over a missing reply file. And a copied blind folder passed until flip.json was
  tied to its own folder. The script can prove a record is consistent, never who wrote a judge reply.
- 2026-11-12, from a 28-round page climb: a judge told to read stills and change nothing cannot save its own
  reply, so the orchestrator retyped about 30 replies by hand to give `tally` its files. That is slow and it is
  the one place a reply can drift. Write each judge's prompt as a file at flip time and have the harness, not
  the orchestrator, save the judge's final message as `judge-N.txt`. Also: on stills, votes follow where a
  screen cut falls and whether the last still repeats the one before, so capture views that cut no line.
- 2026-11-13, t3-switcher-backcast: in judge mode `hc.py baseline` runs the capture `--cmd` with no folder argument,
  while `round` appends the round folder, so a capture script that requires its out dir fails at baseline. Default the
  out dir to `.hillclimb/rounds/r00` in the capture script. Also: a session subagent budget (12) caps judge panels at
  about 3 rounds plus pre-flight; plan the final best-vs-baseline panel into that budget up front.

- 2026-11-13: the agent that climbs should never hold the pen for its own grades. With `--judge-cmd` the judge
  command lives in the locked config and `round` writes every reply from that command's stdout, so a reply in
  the blind folder before the judges ran can only be planted, and is refused (`test/judge-script.sh`).

- 2026-11-13, an offer-page climb: a harness guard can refuse a shell line that loops `claude -p` on a large
  model, and a refused line runs nothing, so a `mkdir` chained in front of the loop never happened and the
  first panel read files that did not exist. Make the folders in their own command first, and when the judge
  command is a loop of headless calls, either use the slim batch route the guard names or run the judges as
  fresh-context subagents and save their replies yourself. A judge told "read only this file" correctly
  refuses to score a missing file; treat that refusal as a setup failure, not a vote.
