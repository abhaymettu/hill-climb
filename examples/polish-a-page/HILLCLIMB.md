# Hill climb: release notes page look

Written 2026-10-27 before round 1. Everything below is fixed for the run.

## Target
The release notes page reads as a calm, well-made product page. Editable: `style.css` only.
Frozen: `index.html` (content and structure), `capture.mjs` (views and gates).

## Baseline
`hill-climb/page@7cd68a4`.

## Score
Mode: composite (gates, then judge).

Judge:
- Views, every round, same order: `desktop` (1280 wide, full page), `mobile` (390 wide, full page)
- Capture: `node capture.mjs .hillclimb/rounds/rNN` (writes desktop.png, mobile.png, gates.json)
- Reference: none (no gold standard for this proof; the rubric carries the bar)
- Rubric, fixed:
  1. Hierarchy: can you tell at a glance what the page is, where each release starts, and what is new?
  2. Readability: line length, line spacing, text size, comfortable to read on both views.
  3. Polish: spacing rhythm, alignment, consistent details; nothing looks accidental.
  4. Restraint: no gimmicks or decoration for its own sake (gradients, glass, shadows everywhere, emoji).
- Judges per round: 3 fresh-context subagents, own coin flip each, strict majority wins, else keep best.

## Gates (veto, checked before the judge)
- Visible text identical to round 0 (`.hillclimb/baseline-text.txt`)
- No horizontal overflow on either view
- WCAG contrast of every text node at least 4.5:1 on both views

## Budget and stop rule
- At most 6 rounds. Stop after 3 rounds in a row without a win.
- Drift check: final best vs baseline with a fresh 3-judge panel.

## Restarts
None.
