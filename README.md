# hill-climb

**Hand your coding agent something to improve, and get back a better version plus a log that proves each step.**

hill-climb is an agent skill. The agent changes one thing at a time, scores it against the current best, keeps
it only if it wins, and reverts it if not. Use it for:

- **Speed and size.** Runtime, bundle bytes, memory, latency: any number a command prints.
- **Quality you can measure.** Test pass rate, model loss, a benchmark score.
- **Taste.** How a page or a piece of copy looks and reads, voted on by blind judges.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.png">
  <img alt="Two real runs. Speed: a benchmark falls from 2.53 s to 0.0068 s over 8 rounds. Look: a release notes page before and after 6 rounds judged blind." src="assets/hero-light.png">
</picture>

## Install

**Claude Code plugin**

```
/plugin marketplace add abhaymettu/hill-climb
/plugin install hill-climb@hill-climb
```

**Or copy the skill folder** (Claude Code, or any agent that reads `SKILL.md` skills)

```sh
git clone https://github.com/abhaymettu/hill-climb
cp -R hill-climb/skills/hill-climb ~/.claude/skills/
```

Needs `git` and Python 3.8+. Handing the repo to an agent? Point it at [AGENTS.md](AGENTS.md).

## Use

Ask in plain words. The skill picks the score mode, writes the setup down, and starts.

```
hill-climb the speed of parse.py; the benchmark is `python bench.py`, tests must pass
hill-climb the landing page look against stripe.com, 10 rounds
shrink the JS bundle, keep `npm test` green, stop after 5 rounds without a win
```

## What a run looks like

A real run from [`examples/speed-up-a-function`](examples/speed-up-a-function): a slow text-stats module,
8 rounds, a 2% minimum gain, tests and an output checksum as gates.

```
round  change                                        seconds  verdict
0      baseline                                      2.5283   baseline
1      dedupe: one-pass dict bucketing               0.0455   keep     gain 98.2%
2      top_tokens: sorted() by key, drop bubble sort 0.0147   keep     gain 67.7%
3      normalize: one re.sub on joined line          0.0108   keep     gain 26.5%
4      tokenize: precompiled findall                 0.0088   keep     gain 18.5%
5      top_tokens: Counter.update                    0.0088   revert   inside the noise band
6      tokenize: lower joined words once             0.0090   revert   inside the noise band
7      normalize: lower once, precompiled regex      0.0077   keep     gain 12.5%
8      top_tokens: one findall over the corpus       0.0068   keep     gain 11.7%
```

2.53 s to 0.0068 s, about 370 times faster, with every kept step measured five times and every
loser reverted. The page above is [`examples/polish-a-page`](examples/polish-a-page): six rounds, three blind
judges per round, one idea (tinted cards with shadows) voted down 0 to 3 and reverted.

## How it works

Before the first round, the agent writes down what it is improving, how it scores a version, which checks must
always pass (tests, build, contrast), and when to stop. That setup never changes mid-run, so every round is
measured the same way.

Each round is one change. If a check fails, the change is reverted. Otherwise it is scored against the current
best: a number is measured several times so noise cannot pass as a win, and taste is decided by three judges who
see both versions side by side without knowing which is new. Winners are kept, losers are reverted, and every
round goes in the log. The full method is in [SKILL.md](skills/hill-climb/SKILL.md).

## Credits

Built on Andrej Karpathy's [autoresearch](https://github.com/karpathy/autoresearch), with ideas from
[uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch) and
[tbelbek/karpathy-autoresearch](https://github.com/tbelbek/karpathy-autoresearch). All MIT.

## License

MIT
