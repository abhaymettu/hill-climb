"""Generate the tinyclf data. Train and validation go to the workspace; the test split stays hidden."""
import sys
from pathlib import Path

import numpy as np


def sample(n, rng):
    X = rng.normal(size=(n, 16))
    X[:, 12:] *= 3.0
    s = (1.4 * X[:, 0] * X[:, 1] + np.sin(2.0 * X[:, 2]) + 0.8 * (X[:, 3] ** 2 + X[:, 4] ** 2 - 2.0)
         + 0.6 * X[:, 5] - 0.5 * np.abs(X[:, 6]) + 0.4 * X[:, 7] * (X[:, 8] > 0))
    y = (s > 0).astype(np.int64)
    flip = rng.random(n) < 0.06
    y[flip] = 1 - y[flip]
    return X.astype(np.float64), y


def main(workspace, hidden):
    rng = np.random.default_rng(20261101)
    Xtr, ytr = sample(1200, rng)
    Xva, yva = sample(400, rng)
    Xte, yte = sample(20000, rng)
    d = Path(workspace) / "data"
    d.mkdir(exist_ok=True)
    np.savez(d / "train.npz", X=Xtr, y=ytr)
    np.savez(d / "val.npz", X=Xva, y=yva)
    np.savez(Path(hidden) / "test.npz", X=Xte, y=yte)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
