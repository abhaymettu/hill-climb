# Hill climb: <target in a few words>

Written <date> before round 1. Everything below is fixed for the run. Changing the score, the gates or the
view set restarts the run at a new round 0; note why at the bottom.

## Target
What gets better, in one sentence. The surface that may change (files, settings) and what stays frozen
(tests, the benchmark, the eval harness, fixtures).

## Baseline
The commit or state that round 0 measures: `<branch>@<sha>`.

## Score
Mode: scalar | judge | composite.

Scalar:
- Command: `<command>` (run from `<dir>`)
- Metric: wall time | regex `<pattern>` on its output
- Direction: min | max
- Runs per measurement: 5 (warmup 1). Minimum gain that counts: 2%.

Judge:
- Views captured every round, same order, same size: `<view 1>`, `<view 2>`
- Capture command: `<command>` writing to `.hillclimb/rounds/rNN/`
- Reference (optional): `<path or URL>`
- Rubric, 3 to 5 axes, fixed: 1. ... 2. ... 3. ...
- Judges per round: 3 fresh contexts, majority wins, ties keep the best.

## Gates (veto, checked before the score)
- `<test command>` passes
- `<build or type check>` passes
- `<guard metric>` no worse than baseline by more than <x>

## Budget and stop rule
- At most <N> rounds or <T> wall-clock, whichever comes first.
- Stop after <P> rounds in a row without a win, or when <target value> is reached.
- One heavy job at a time.

## Ideas queue (optional, ordered)
1. ...

## Restarts
None yet.
