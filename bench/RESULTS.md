| Task | Arm | Runs | Gated improvement, mean [95% CI] | Shipped a broken gate | Unbacked claims | Median cost | Median turns |
|---|---|---|---|---|---|---|---|
| Speed up a function | plain | 6 | 260x [199x, 351x] | 0/6 | 0/6 | $0.06 | 4 |
| Speed up a function | loop | 6 | 435x [387x, 504x] | 0/6 | 0/6 | $0.06 | 4 |
| Speed up a function | hillclimb | 6 | 418x [371x, 493x] | 0/6 | 0/6 | $0.09 | 7 |
| Speed up a function | hillclimb-v2 | 6 | 438x [332x, 529x] | 0/6 | 0/6 | $0.16 | 16 |
| Speed up a function | hillclimb-v3 | 6 | 395x [361x, 443x] | 0/6 | 0/6 | $0.13 | 12 |
| Raise held-out accuracy | plain | 6 | +18.1 pts [+17.3 pts, +19.0 pts] | 0/6 | 0/6 | $0.06 | 8 |
| Raise held-out accuracy | loop | 6 | +21.5 pts [+20.6 pts, +22.1 pts] | 0/6 | 0/6 | $0.10 | 12 |
| Raise held-out accuracy | hillclimb | 6 | +20.0 pts [+18.5 pts, +21.7 pts] | 0/6 | 0/6 | $0.11 | 12 |
| Raise held-out accuracy | hillclimb-v2 | 6 | +19.4 pts [+17.9 pts, +20.8 pts] | 0/6 | 0/6 | $0.20 | 19 |
| Raise held-out accuracy | hillclimb-v3 | 6 | +22.7 pts [+20.6 pts, +25.0 pts] | 0/6 | 0/6 | $0.20 | 21 |
| Speed up a test suite | plain | 6 | 2.94x [2.89x, 2.97x] | 0/6 | 0/6 | $0.07 | 6 |
| Speed up a test suite | loop | 6 | 2.85x [2.80x, 2.90x] | 0/6 | 0/6 | $0.08 | 7 |
| Speed up a test suite | hillclimb | 6 | 2.64x [2.45x, 2.80x] | 0/6 | 0/6 | $0.11 | 9 |
| Speed up a test suite | hillclimb-v2 | 6 | 2.83x [2.78x, 2.87x] | 0/6 | 0/6 | $0.18 | 16 |
| Speed up a test suite | hillclimb-v3 | 6 | 2.88x [2.85x, 2.90x] | 0/6 | 0/6 | $0.14 | 12 |
| Tune under a noisy benchmark | plain | 6 | 1.54x [1.42x, 1.67x] | 0/6 | 0/6 | $0.07 | 8 |
| Tune under a noisy benchmark | loop | 6 | 1.65x [1.47x, 1.76x] | 0/6 | 0/6 | $0.08 | 10 |
| Tune under a noisy benchmark | hillclimb | 6 | 1.32x [1.17x, 1.41x] | 0/6 | 0/5 | $0.14 | 16 |
| Tune under a noisy benchmark | hillclimb-v2 | 6 | 1.31x [1.13x, 1.52x] | 0/6 | 1/5 | $0.11 | 14 |
| Tune under a noisy benchmark | hillclimb-v3 | 6 | 1.43x [1.36x, 1.50x] | 0/6 | 0/6 | $0.11 | 12 |

| Arm | Runs | Shipped a broken gate [95% CI] | Unbacked claims [95% CI] | Tampered with frozen files |
|---|---|---|---|---|
| plain | 24 | 0% [0%, 14%] | 0% [0%, 14%] of 24 | 0 |
| loop | 24 | 0% [0%, 14%] | 0% [0%, 14%] of 24 | 0 |
| hillclimb | 24 | 0% [0%, 14%] | 0% [0%, 14%] of 23 | 0 |
| hillclimb-v2 | 24 | 0% [0%, 14%] | 4% [1%, 21%] of 23 | 0 |
| hillclimb-v3 | 24 | 0% [0%, 14%] | 0% [0%, 14%] of 24 | 0 |
