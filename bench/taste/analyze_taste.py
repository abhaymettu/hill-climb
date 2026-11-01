"""Summarize the headline judging: do blind judges agree with each other, and with the real A/B winner?

    python bench/taste/analyze_taste.py     # writes bench/taste/TASTE.md and taste.json
"""
import json
import math
import random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = ["haiku", "sonnet", "opus"]


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, mid - half, mid + half


def fleiss(table):
    """Fleiss' kappa; table is a list of per-item category counts with the same number of raters."""
    n = sum(table[0])
    N = len(table)
    cats = len(table[0])
    p_j = [sum(row[j] for row in table) / (N * n) for j in range(cats)]
    P_i = [(sum(c * c for c in row) - n) / (n * (n - 1)) for row in table]
    Pbar, Pe = sum(P_i) / N, sum(p * p for p in p_j)
    return (Pbar - Pe) / (1 - Pe) if Pe < 1 else float("nan")


def label(v):
    return "tie" if v["picked_winner"] is None else ("win" if v["picked_winner"] else "lose")


def panel(model):
    path = HERE / f"verdicts-{model}.jsonl"
    if not path.exists():
        return None
    by_pair = {}
    for line in open(path):
        v = json.loads(line)
        by_pair.setdefault(v["pair"], []).append(v)
    full = {p: vs for p, vs in by_pair.items() if len(vs) == 3}
    calls = [v for vs in full.values() for v in vs]
    single_right = sum(v["picked_winner"] is True for v in calls)
    single_decided = sum(v["picked_winner"] is not None for v in calls)
    slot_a = sum(v["verdict"] == "A" for v in calls)
    slot_decided = sum(v["verdict"] in ("A", "B") for v in calls)
    majority = {}
    for p, vs in full.items():
        c = Counter(label(v) for v in vs)
        majority[p] = "win" if c["win"] >= 2 else ("lose" if c["lose"] >= 2 else "none")
    maj_right = sum(m == "win" for m in majority.values())
    maj_decided = sum(m != "none" for m in majority.values())
    unanimous = [p for p, vs in full.items() if len({label(v) for v in vs}) == 1 and label(vs[0]) != "tie"]
    unan_right = sum(label(full[p][0]) == "win" for p in unanimous)
    kappa = fleiss([[Counter(label(v) for v in vs)[k] for k in ("win", "lose", "tie")] for vs in full.values()])
    return {"pairs": len(full), "calls": len(calls),
            "single_acc": wilson(single_right, len(calls)), "single_acc_decided": wilson(single_right, single_decided),
            "majority_acc": wilson(maj_right, len(full)), "majority_decided": maj_decided,
            "unanimous": len(unanimous), "unanimous_acc": wilson(unan_right, len(unanimous)),
            "fleiss_kappa": kappa, "slot_a_rate": wilson(slot_a, slot_decided),
            "ties": sum(v["picked_winner"] is None for v in calls), "majority": majority}


def boot_kappa(model, n=2000):
    path = HERE / f"verdicts-{model}.jsonl"
    by_pair = {}
    for line in open(path):
        v = json.loads(line)
        by_pair.setdefault(v["pair"], []).append(v)
    rows = [[Counter(label(v) for v in vs)[k] for k in ("win", "lose", "tie")] for vs in by_pair.values() if len(vs) == 3]
    rng = random.Random(0)
    reps = sorted(fleiss([rng.choice(rows) for _ in rows]) for _ in range(n))
    return reps[int(0.025 * n)], reps[int(0.975 * n) - 1]


def pct(t):
    return f"{t[0]:.0%} [{t[1]:.0%}, {t[2]:.0%}]"


def main():
    res = {m: panel(m) for m in MODELS}
    res = {m: r for m, r in res.items() if r}
    lines = ["| Panel (3 judges) | Pairs | One judge picks the real winner | Panel majority picks it | "
             "Unanimous panels | Accuracy when unanimous | Judge agreement (Fleiss kappa) | Picks slot A |",
             "|---|---|---|---|---|---|---|---|"]
    for m, r in res.items():
        klo, khi = boot_kappa(m)
        r["fleiss_ci"] = [klo, khi]
        lines.append(f"| {m} | {r['pairs']} | {pct(r['single_acc'])} | {pct(r['majority_acc'])} | {r['unanimous']} | "
                     f"{pct(r['unanimous_acc'])} | {r['fleiss_kappa']:.2f} [{klo:.2f}, {khi:.2f}] | {pct(r['slot_a_rate'])} |")
    if len(res) > 1:
        lines += ["", "| Panels | Same majority verdict |", "|---|---|"]
        ms = list(res)
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                a, b = res[ms[i]]["majority"], res[ms[j]]["majority"]
                common = [p for p in a if p in b]
                same = sum(a[p] == b[p] for p in common)
                lines.append(f"| {ms[i]} vs {ms[j]} | {pct(wilson(same, len(common)))} |")
    md = "\n".join(lines)
    (HERE / "TASTE.md").write_text(md + "\n")
    for r in res.values():
        r.pop("majority")
    (HERE / "taste.json").write_text(json.dumps(res, indent=1))
    print(md)


if __name__ == "__main__":
    main()
