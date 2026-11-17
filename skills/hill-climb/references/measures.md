# Building the measure

Read the part for your kind of work before setup. Every kind ends in the same three things, written in
HILLCLIMB.md before round 1: a score that is frozen, gates that veto, and a stop rule. If you cannot say how a
round would lose, you do not have a measure yet.

| Kind of work | Score | Typical gates | Freeze |
|---|---|---|---|
| A number from a command | the number, repeated runs | tests, output checksum, a guard metric | the command, inputs, machine |
| A review or rubric gate | open findings at or above the bar | tests, build, conformance, memory cap | the reviewer, its scope, the bar, the ledger |
| Taste | blind pairwise panel | contrast, overflow, links, light and dark both render | views, judge prompt, judge count |
| Low-level code | timing or size, after correctness | sanitizers, property or differential tests | corpus, flags, compiler, CPU |
| Mixed | one primary score; the rest are gates | everything else | all of the above |

## A number from a command

Speed, size, loss, latency, a benchmark score. SKILL.md sections 2 to 4 cover it. Before setup, check three
things: the command does the same work every run (fixed input, fixed seed), the number is the one the user cares
about (p95, not the mean, if tail latency is the complaint), and one thing that must not get worse is a gate
(memory when climbing speed, accuracy when climbing size). For a model or benchmark number on a fixed set, use
the holdout in SKILL.md "Climbing on a fixed eval set".

## A review or rubric gate

The work must pass a reviewer (a code review that says pass or fix, an audit, a correctness checklist). The
trap: a reviewer is a sampler, not a census. Each pass reads the code again and notices different things, so
"fix what the review said, review again" can run forever with the count falling and never reaching zero.

1. **Freeze the reviewer.** Same model or person, same prompt, same scope (the diff against one named base
   commit), same rubric. Write them down. If the base moves (a rebase), that is a measure change.
2. **Set the bar before reading any finding.** Rate each finding on how often it bites and how bad it is, on
   one scale. Findings at or above the bar must close; those below are listed in the report and the code stays.
   Security, data loss and anything that acts on the outside world are always above the bar.
3. **Take a census at round 0.** Run the frozen review two or three times on the baseline (or once each with
   two different models) and merge the findings into a ledger, `.hillclimb/findings.tsv`: id, file and line,
   the claim in one line, rating, first seen at which round, status (open, closed, below-bar, disputed). Extra
   baseline reviews cost less than extra rounds.
4. **The score is the count of open ledger findings at or above the bar** (direction min, min-delta 0). The
   target is zero with every gate green.
5. **One finding per round, with its own check.** Before the fix, write the smallest check that fails because
   of the finding (a test, a repro input, a query). The round is kept when that check passes, the gates pass,
   and no closed finding reopens. A fix whose check still fails is reverted, not patched in place. Fixes of
   one class (the same mistake in several places) may share a round if each has its own check.
6. **A finding with no possible check is a dispute, not a task.** Rule on it in writing (the finding is right,
   or the code is right and why), mark it disputed with the reason, and let the user overrule it. Do not fix
   what you cannot show was broken.
7. **New findings from a later review.** Sort each into one of two piles before doing anything:
   - caused by this round's change: the round loses unless its own fix is trivial; revert and try another way;
   - already present at baseline and only now noticed: add it to the ledger with "first seen rN". It does not
     count against the round, and it is logged as a measure change because the denominator grew.
   If two reviews in a row find new baseline problems at or above the bar, the census was too thin: stop
   climbing, take a wider census, restart the count.
8. **Review last.** A full review is the expensive step. Run each finding's own check and the gates after
   every round; run the frozen review only when the ledger says zero open, as the final measurement.

## A score table (labelled cases)

When the score is "cases the code gets right" against hand labels, the labels are part of the ruler.

- Freeze the cases, the labels and the checks by hash before round 1. Adding a case or a check mid-run is a
  measure change: 10 of 10 on ten easy cases and 19 of 21 after eleven harder ones were added are not a drop,
  and not comparable.
- Always write a score with its denominator and the commit it was measured at: `19/21 @ a1b2c3d`.
- When a label and the code disagree, one of them is wrong. Decide which from the case's facts, never from
  which is cheaper to change, and write the ruling. Changing the label is a measure change; changing the code
  is a round. A label written by the same hand that wrote the code proves only that the code does what its
  author meant, so say so beside the score, and get labels from someone else (or blind) when you can.

## Taste

UI, copy, design, a README's look. Blind pairwise judges, see `judging.md`. Capture every view the reader will
see: light and dark, narrow and wide, the empty and the full state. Gates are the things a judge misses or
cannot see: text contrast, no overflow, links resolve, nothing clipped. If a reader is colour-blind, gate on
lightness difference between colours that carry meaning, and on the meaning also being in text or shape. For
copy, gate on the facts: every number and name in the candidate is in the source.

## Low-level code

Parsers, allocators, kernels, lock-free code, anything where a fast wrong answer is easy.

- Correctness is a gate before any speed number exists: the test suite under sanitizers (address, undefined
  behaviour, thread where threads are involved), plus a property or differential test against a slow reference
  on generated inputs. A round that fails any of them is a loss whatever it scored.
- Fix the instrument: one machine, the same compiler and flags, a pinned CPU or a quiet machine, a warmup, at
  least 5 runs, and an output checksum (`--expect-line`) so the work cannot be optimized away.
- Measure the thing the user runs. A micro-benchmark win that vanishes in the real program is a loss; keep one
  end-to-end number as the score or as a guard.
- Read SKILL.md section 4 on noise before trusting a gain under 5%.

## Mixed measures

A change that must pass a review, hold a score table and stay under a memory cap has three measures. Pick one
as the score (usually the findings count, because it is what blocks) and make every other one a gate with a
fixed threshold: the table may not drop below its baseline, the tests pass, the cap holds. Never trade a gate
for score, and never add up unlike things into one number.

## When a round is expensive

Remote machines, long builds, paid reviews. Spend the cheap checks first and the costly ones last: the
finding's own check, then the fast gates, then the slow gates, then the review. Keep the budget small (3 to 5
rounds) and the patience at 1: a round that does not lower the score ends the run, and what is left goes in
the report with its ratings. Say what a round will cost before starting it.

## When the measure has to change

Sometimes it must: a label was wrong, the base moved, a check was missing. Do not carry on silently and do not
throw the run away. Log a `measure-change` row (what changed, why, who ruled), re-measure the current best
under the new measure, and write both values for that one commit. Numbers on the two sides of the line are
never compared. This is not a round and it never counts as a win.
