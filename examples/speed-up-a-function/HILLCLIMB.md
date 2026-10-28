# Hill climb: textstats.py speed

Written 2026-10-27 21:40 before round 1. Everything below is fixed for the run.

## Target
Lower runtime of top_tokens + duplicate_groups as timed by bench.py. Editable: textstats.py only.
Frozen: bench.py, test_textstats.py.

## Baseline
hill-climb/textstats-speed@f539398

## Score
Mode: composite (scalar + gates).
- Command: `python3 bench.py` (run from repo root)
- Metric: regex `seconds=([0-9.]+)`
- Direction: min
- Runs per measurement: 5 (warmup 1). Minimum gain that counts: 2%.

## Gates (veto, checked before the score)
- `python3 test_textstats.py` exits 0
- `python3 bench.py` prints exactly the line `check top=('user', 3000) groups=96 largest=47`

## Budget and stop rule
- At most 8 rounds. Stop after 3 rounds in a row without a win. One heavy job at a time.

## Ideas queue
1. duplicate_groups: bucket by normalized key in one pass (O(n)) instead of O(n^2) with list membership
2. top_tokens: sort with key instead of bubble sort; Counter
3. tokenize: precompiled regex / findall
4. normalize: precompiled regex

## Restarts
None yet.
