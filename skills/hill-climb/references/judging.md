# Blind pairwise judging

Use this when "better" is a matter of taste or quality that no command can measure: a page's look, an
illustration, copy, an API's ergonomics, a prompt's outputs. The judge compares the candidate with the
current best. Absolute scores drift between calls; a side-by-side choice is much steadier.

## Per round

1. Capture the candidate's artifacts with the same capture step as every other round (same views, same
   order, same size, same data). Put them in `.hillclimb/rounds/rNN/`. The best's artifacts are already on
   disk from the round it won, so you never re-render the old version.
2. Run `hc.py flip --judges N --best <best dir> --cand <cand dir> --out .hillclimb/rounds/rNN/blind`
   **before** any judge runs. Each judge gets its own coin flip, which cancels position bias across the
   panel, and its own copies under `judge-N/A/` and `judge-N/B/`. File paths unblind as surely as labels
   (`r00/` vs `r07/`), so judges only ever see the blind copies. The mapping goes to `blind/flip.json`.
3. Start N judges, each a fresh context that has never seen the work in progress: a subagent, or a headless
   model call. Never judge in the context that made the change; the builder grades its own work kindly.
   Run them in parallel when you can; they are independent.
4. Each judge gets exactly: the frozen prompt (`.hillclimb/judge-prompt.md`, written from the template
   below), the paths of its A and B copies, and the reference if the setup names one, plus the line "do not
   read any other file". Nothing about which is new, what changed, or why.
5. Unblind with the recorded mapping. The candidate wins the round only with a strict majority of the
   judges preferring it overall. A tie, a split, or "no difference" keeps the best.

## Panel size

- 3 judges is the default. It turns a coin-flippy single opinion into a vote and costs three small calls.
- 1 judge is acceptable when calls are expensive and the run is long; expect more false wins, and lean on
  the final confirmation below.
- 5 judges when two candidates are close and the decision matters (the last few rounds, a large move).

## Judge prompt (fill the brackets, keep the rest identical every round)

```
You are judging two versions of [what it is], labelled A and B. [If a reference is attached: the
reference shows the quality and feel we are aiming for; it is a target, not something to copy.]

For each view, look at A and B side by side. Then score A and B from 1 to 10 on each axis, with one line
of evidence per score that points at something specific you can see (an element, a region, a number):

1. [axis]
2. [axis]
3. [axis]

Then give an overall verdict: A, B, or TIE. Choose TIE only if you cannot tell them apart in a way that
matters. Be decisive otherwise. Reply in this exact form:

AXES
A: [axis 1 score], [axis 2 score], ...
B: [axis 1 score], [axis 2 score], ...
EVIDENCE
- ...
VERDICT: A | B | TIE
```

Ask for scores per axis even though only the verdict decides: the evidence lines show *why* a round was
lost, and a pattern there (readability lost three rounds running) tells you what to try next.

## Keeping the climb honest

- **Fixed views.** A judge can only compare what it sees. If a change helps one state and hurts another,
  the view set must contain both, from round 0. Adding a view mid-run restarts the run.
- **Pairwise wins do not chain.** A beats B and B beats C does not prove A beats C, and many small
  wins can drift somewhere nobody asked for. Every 5 wins, and always at the end, judge best vs the
  round-0 baseline with a fresh panel. If baseline wins or ties, report it plainly; the climb went sideways.
- **Gates before taste.** Run the hard gates (tests, contrast, layout shift, size budgets) first. A
  candidate that fails a gate is a loss without spending judge calls.
- **One reference, or two.** A reference anchors the rubric. Two references keep the climb from cloning
  either one.

## Without subagents

Any fresh model context works as a judge: a headless CLI call with the images attached, or an API call.
What matters is that it has no memory of the work in progress and no hint of which side is new.
