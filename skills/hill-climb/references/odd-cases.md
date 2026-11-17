# Odd cases

Read the part you need. The loop in SKILL.md does not change; these are its less common shapes.

## Ports and rewrites: parity first, then speed

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

## Parallel candidates


When rounds are slow and ideas are independent, try 2 or 3 candidates per round in separate git worktrees
(or subagents, each on its own branch). Score each against the same best and keep only the single best
winner. Then the next round starts from it. Keep it bounded: never more than 3 at once, and never run
heavy jobs (builds, benchmarks, renders) in parallel with each other when the score is a timing, since
they distort each other's numbers.

## A round by hand

Without `round` (no config, an unusual score, a findings run, or a target on a remote machine or in someone
else's repo, where the log lives in your own folder instead), do the same steps by hand, in this order: commit
(`git commit -am "r07: <change>"`); run the gates, any failure is a loss; `hc.py measure --runs 5 --regex
'<re>' --out .hillclimb/rounds/r07.json -- <cmd>`; `hc.py compare .hillclimb/rounds/best.json
.hillclimb/rounds/r07.json --direction min --min-delta 0.02`; `hc.py log .hillclimb/results.tsv round=7
change="..." score=<median> gates=pass verdict=keep|revert notes="..."` before reverting, so the row holds
the candidate's commit; on a keep copy the JSON to `best.json`, otherwise `git reset --hard HEAD~1`;
`hc.py status .hillclimb/results.tsv --patience 5 --budget 20`.

## Runs set up before locks

A run set up before locks existed has none: hc.py prints one `legacy run` line and keeps the old checks
(and `--verdict`). Let them finish; start new runs with `setup`.
