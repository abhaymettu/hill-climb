"""Summarize a corpus of log lines: near-duplicate groups and top tokens."""
import re


def tokenize(line):
    out = []
    for w in re.split(r"[^A-Za-z0-9]+", line):
        if w != "":
            out.append(w.lower())
    return out


def top_tokens(lines, k=10):
    counts = {}
    for line in lines:
        for t in tokenize(line):
            if t in counts.keys():
                counts[t] = counts[t] + 1
            else:
                counts[t] = 1
    items = list(counts.items())
    for i in range(len(items)):
        for j in range(len(items) - 1 - i):
            a, b = items[j], items[j + 1]
            if (b[1], a[0]) > (a[1], b[0]):
                items[j], items[j + 1] = b, a
    return items[:k]


def normalize(line):
    return " ".join(re.sub(r"\d+", "#", t) for t in tokenize(line))


def duplicate_groups(lines):
    """Groups of line indexes whose normalized text is identical, groups of 2+, in first-seen order."""
    groups = []
    used = []
    for i in range(len(lines)):
        if i in used:
            continue
        g = [i]
        for j in range(i + 1, len(lines)):
            if j not in used and normalize(lines[i]) == normalize(lines[j]):
                g.append(j)
                used.append(j)
        if len(g) > 1:
            groups.append(g)
    return groups
