"""Train on data/train.npz, report accuracy on data/val.npz. Training must finish within 20 seconds."""
import time

import numpy as np

import model


def main():
    tr = np.load("data/train.npz")
    va = np.load("data/val.npz")
    t0 = time.perf_counter()
    m = model.fit(tr["X"], tr["y"])
    secs = time.perf_counter() - t0
    acc = float((model.predict(m, va["X"]) == va["y"]).mean())
    print(f"val_acc={acc:.4f}")
    print(f"train_seconds={secs:.2f}")
    if secs > 20:
        raise SystemExit("training took longer than 20 seconds")


if __name__ == "__main__":
    main()
