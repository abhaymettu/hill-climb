# Lessons from real runs

Newest last. Add one when a run shows a gap the skill let through.

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
- 2026-11-13, t3-switcher-backcast: a session subagent budget (12) caps judge panels at about 3 rounds plus
  pre-flight; plan the final best-vs-baseline panel into that budget up front.

- 2026-11-13: the agent that climbs should never hold the pen for its own grades. With `--judge-cmd` the judge
  command lives in the locked config and `round` writes every reply from that command's stdout, so a reply in
  the blind folder before the judges ran can only be planted, and is refused (`test/judge-script.sh`).

- 2026-11-13, an offer-page climb: a harness guard can refuse a shell line that loops `claude -p` on a large
  model, and a refused line runs nothing, so a `mkdir` chained in front of the loop never happened and the
  first panel read files that did not exist. Make the folders in their own command first, and when the judge
  command is a loop of headless calls, either use the slim batch route the guard names or run the judges as
  fresh-context subagents and save their replies yourself. A judge told "read only this file" correctly
  refuses to score a missing file; treat that refusal as a setup failure, not a vote.

- 2026-11-17, a code change that had to pass a review gate on a remote box: three review rounds each said
  fix, the findings went 14 to 4 and every review raised ones the last had not, and the score table read
  10 of 10 and later 19 of 21 because cases and checks were added under it. Nothing was frozen, so no round
  could be called a win or a loss. A reviewer samples; take a census at round 0, set the bar first, keep a
  ledger, give each fix its own check, and count the review on the whole change (`references/measures.md`).
- 2026-11-17, the same change, climbed under this skill: the gate was a tool with its own pass rule (no
  finding at its two top severities), so the bar was the reviewer's severity and the plan to leave the
  low-rated findings would never have passed. One census review at the baseline found a fifth finding before
  round 1 instead of after the last round; it ran in a detached copy, because the review tool overwrites the
  receipt the gate reads. Three fresh agents given only this skill and a one-line task (copy, low-level code, a
  model score) each set up a frozen score, gates and a stop rule; all three would have let hc.py commit in a
  parent repo, and half the body did not apply to any one of them, so the body now carries the loop only.
- 2026-11-17, review gate, tie on a count: the frozen keep rule was "fewer HIGH plus MEDIUM than before". The last
  round removed the only HIGH and the review named four new MEDIUM, 4 against 4, so the rule reverted a round that
  was arguably better, and changing the rule after seeing the result was not allowed. When a gate has severities,
  freeze how they rank with the measure (compare HIGH first, then MEDIUM), and say what a tie does.
- 2026-11-17, review gate, raw counts from a sampling reviewer: the frozen rule compared one review's count with
  the next. Twice a round closed every finding it was sent for and its review named as many others on lines the
  round never touched, so the raw counts tied and the rule reverted the better head (once undone by a ruling,
  once not: the branch ended with four known findings beside a tag with two). Charge untouched-line findings to
  the kept head before comparing, freeze the keep rule in charged counts, and when the count stops falling
  across reviews call it a floor and hand the findings over (measures.md, review gate, step 8).
