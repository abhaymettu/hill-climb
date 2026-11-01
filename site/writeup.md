# I benchmarked my own agent skill, and it found two bugs in it

hill-climb is a skill for coding agents. You hand the agent something to improve (a slow function, a model's
accuracy, a test suite's runtime) and it works in rounds: change one thing, score it against the current best,
keep it if it wins, revert it if not, log it. It is Andrej Karpathy's autoresearch loop, packaged with gates that
veto a round, a noise band for flaky numbers, and a blind judge panel for taste work.

Lots of people ship recipes like this. I could not find one that tests whether the recipe helps, so I built a
benchmark.

## The setup

Four small tasks, each with a score the agent can run and a hidden gate it never sees:

- **Speed up a log analyzer.** Hidden gate: edge-case tests and a differential test against the original.
- **Raise a numpy classifier's accuracy.** The agent sees a 400-row validation split. The score is a hidden
  20,000-row test split.
- **Speed up a pytest suite.** Hidden gate: 15 mutants of the library that the original suite kills. A faster suite
  that stops catching bugs fails.
- **Tune six settings of a simulated service** whose benchmark varies about 8% from run to run. The score is the
  true, noise-free p95 latency.

Three kinds of agent got the same task: the bare task ("plain"), the task plus "keep iterating, do not stop early"
("loop"), and the task plus the skill. Every run was a fresh `claude -p` session with my settings, skills,
hooks and memory off, scored from outside. That is 120 runs on Claude Sonnet across five
arms and 36 on Claude Opus across three. Every transcript is in the repo.

## The result I trust most

On Opus, the test-suite task split the arms. The suite builds a 400,000-item inventory for every test. The good fix
is to build it once. The cheap fix is to build less of it.

5 of 8 Opus runs without the skill took the cheap fix. They shrank the inventory to between 2,000 and 20,000 items,
and their own summaries said the suite covered the same behavior: "same assertions", "still covers every
price/qty combination". Their suites passed and killed 14 of 15 hidden mutants. The one they lost truncates tag
lookups past 150,000 results, a bug only a big inventory can show. Raw, those suites were 25 to 64 times faster.
Counted honestly, they were worth nothing.

With the skill, 0 of 4 runs did this, and that arm had the best real speedup of the three (2.83x).

It is 5 of 8 against 0 of 4 (a two-sided Fisher p of about 0.08), and one
mutant carries it. But it is the failure I care about most in agent work: not a crash, not a lie, but a confident
summary of a change that quietly gave something up.

## What it did not do

On the easier tasks the skill tied a plain loop. Sonnet sped up the log analyzer 260x to 438x in every arm, gained
18 to 23 accuracy points, and sped up the suite 2.6x to 2.9x. No Sonnet run in any arm broke a gate. The skill cost
about twice as much per run, because it measures more.

On the noisy tuning task, the one the skill is built for, it lost. The first two versions reached 1.32x and 1.31x
against 1.65x for the plain loop, and three of their twelve runs ended exactly where they started.

## The benchmark debugged the skill

That noisy-task result sent me into the transcripts, and both causes were in my helper script, not the agents.

First, stale bytecode. Agents ran rounds back to back, so a revert and the next edit could land in the same second
with the same file size. Python caches compiled modules by modification time in whole seconds plus size, so the
next measurement ran the previous round's settings.

Second, the noise band. Version 2 called something a win only if it beat twice the summed median absolute deviation
of both measurements. That number does not shrink as you add runs, so no amount of measuring could resolve a small
gain. At 8% noise the band was 15 to 27%.

Version 3 clears the bytecode cache and waits out the second after a revert, and uses two standard errors of the
difference of medians, which shrinks with more runs. The baseline step now tells the agent when its measurement is
too noisy and how many runs would fix it. On the noisy task v3 moved to 1.43x with no run stuck at baseline. It
still trails the free-form loop, whose agents wrote little search scripts that averaged runs while skill agents
tuned one knob per round. That gap is the next thing to fix.

An earlier round of the benchmark had already changed the skill once. Version 1 agents stopped after one big win
and skipped the bookkeeping. Version 2 made each round a single command and says outright that a big win is not a
stop rule. Logged rounds went from a median of 3 to 7.

## Do blind judges know good copy?

The skill judges taste work with three fresh model judges who see two versions under neutral labels. I checked
that protocol against 100 real Upworthy headline A/B tests with a clear winner. Panels of Haiku, Sonnet and Opus
agreed with each other more as models grew (Fleiss kappa 0.45 to 0.83), but every panel picked the real winner only
65 to 69% of the time, and a majority of three did no better than a single judge. The judges share their mistakes.
The skill's judging guide now tells agents to report a panel win as "the judges preferred it", never as "users will".

## Try it

```
/plugin marketplace add abhaymettu/hill-climb
/plugin install hill-climb@hill-climb
```

The code, all 156 runs, the scorer and a 10-page paper are at
[github.com/abhaymettu/hill-climb](https://github.com/abhaymettu/hill-climb).
