# Climbing on a fixed eval set

When the score is accuracy on a fixed set (a validation split, a prompt eval, a benchmark suite), every
kept round fits that set a little. Twenty rounds of small wins on 400 examples can be pure fit.

- Choose settings (hyperparameters, thresholds, prompt wording variants) inside the training data, with
  cross-validation, and let the eval set only decide the round. Never sweep a setting against the eval set.
- Prefer larger, principled changes over tuning a number to the third decimal.
- Before round 0, set aside about 20% of the real set as a holdout, add its path to `--frozen`, and pass
  `--holdout-cmd '<the score command on the holdout>'`. Never open those files again. hc.py runs it at
  baseline, after every 5th win and at the end. If the visible score climbed and the holdout did not, it
  prints `STOP: overfitting`: stop and report both numbers. Judge runs: the holdout command captures held-out
  views; hc.py flips best against baseline on them and, with `--judge-cmd`, judges them on the spot;
  without it, it waits for a panel (`hc.py holdout --panel`).
- In the report, call the final number what it is: the score on the set you climbed on, which overstates
  performance on new data, and give the holdout number beside it.
- Generated data has no files to hide: the holdout is a list of seeds the climb never runs. Freeze the
  generator and the seed list, and let only `--holdout-cmd` use those seeds.
- Nothing checks that a setting was chosen inside the training data, so say in the round's log row how it
  was chosen.
