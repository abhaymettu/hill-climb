"""Summarize a corpus of log lines: near-duplicate groups and top tokens."""
import re
from collections import Counter


_WORD = re.compile(r"[A-Za-z0-9]+")
_DIGITS = re.compile(r"\d+")


def tokenize(line):
    return [w.lower() for w in _WORD.findall(line)]


def top_tokens(lines, k=10):
    counts = Counter(" ".join(_WORD.findall("\n".join(lines))).lower().split())
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:k]


def normalize(line):
    return _DIGITS.sub("#", " ".join(_WORD.findall(line)).lower())


def duplicate_groups(lines):
    """Groups of line indexes whose normalized text is identical, groups of 2+, in first-seen order."""
    buckets = {}
    for i, line in enumerate(lines):
        buckets.setdefault(normalize(line), []).append(i)
    return [g for g in buckets.values() if len(g) > 1]
