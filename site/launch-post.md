# Launch post draft (for Abhay to send himself)

Ask a coding agent to make your tests faster and it can get there by testing less. I built a skill that
makes it work in careful rounds instead (change one thing, measure, keep or revert, log), then built a benchmark to
see whether that helps: four tasks, each with a hidden check the agent never sees, 156 isolated Claude Code runs.

On Opus, 5 of 8 runs without the skill sped up a test suite by shrinking its fixture until it missed
a hidden bug, and said the suite covered the same behavior. With the skill, 0 of 4.

On easy tasks it ties a plain "keep iterating" prompt at about twice the cost, and on a noisy
tuning task it still trails one.

The benchmark also found two bugs in my own helper script (stale bytecode, a noise band more runs could never
shrink). Both are fixed. And blind LLM judge panels picked the real winner of 100 Upworthy headline tests only
65 to 69% of the time, however much they agreed.

Code, all transcripts, and a paper: https://github.com/abhaymettu/hill-climb
