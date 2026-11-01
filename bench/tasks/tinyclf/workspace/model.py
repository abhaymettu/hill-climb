"""A binary classifier. eval.py calls fit(X, y) on the training split and predict(model, X) on new rows.

X is a float array of shape (n, 16), y is 0/1 of shape (n,). numpy is the only dependency available.
"""
import numpy as np


def fit(X, y, lr=0.1, epochs=200):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    w = np.zeros(Xb.shape[1])
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-Xb @ w))
        w -= lr * Xb.T @ (p - y) / len(y)
    return w


def predict(model, X):
    Xb = np.hstack([X, np.ones((len(X), 1))])
    return (Xb @ model > 0).astype(np.int64)
