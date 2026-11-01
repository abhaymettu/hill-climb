"""Build headline pairs with a known real-world winner from the Upworthy Research Archive.

    python bench/taste/pairs.py   # downloads the exploratory file (14 MB, CC BY 4.0) into bench/taste/data/

Each pair is two headlines that ran in the same A/B test with the same image, excerpt and lede, so only the
words differ. A pair is kept only when the click-rate gap is large (two-proportion z of at least 3).
Matias, Munger, Aubin Le Quere and Ebersole, "The Upworthy Research Archive", Scientific Data 8, 2021.
"""
import csv
import json
import math
import random
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "https://osf.io/download/3vqmp/"
N_PAIRS = 100


def z_two_prop(c1, n1, c2, n2):
    p = (c1 + c2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return (c1 / n1 - c2 / n2) / se if se else 0.0


def main():
    src = HERE / "data" / "upworthy-exploratory.csv"
    if not src.exists():
        src.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(URL, src)
    tests = defaultdict(list)
    with open(src, newline="") as f:
        for row in csv.DictReader(f):
            if row["headline"] and int(row["impressions"] or 0) >= 1000:
                tests[row["clickability_test_id"]].append(row)
    pairs = []
    for tid, rows in sorted(tests.items()):
        best = None
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                if a["headline"].strip() == b["headline"].strip():
                    continue
                if (a["eyecatcher_id"], a["excerpt"], a["lede"]) != (b["eyecatcher_id"], b["excerpt"], b["lede"]):
                    continue
                z = z_two_prop(int(a["clicks"]), int(a["impressions"]), int(b["clicks"]), int(b["impressions"]))
                if abs(z) >= 3 and (best is None or abs(z) > abs(best[2])):
                    best = (a, b, z)
        if best:
            a, b, z = best
            win, lose = (a, b) if z > 0 else (b, a)
            pairs.append({"test_id": tid, "winner": win["headline"].strip(), "loser": lose["headline"].strip(),
                          "ctr_winner": int(win["clicks"]) / int(win["impressions"]),
                          "ctr_loser": int(lose["clicks"]) / int(lose["impressions"]), "z": abs(z)})
    random.Random(0).shuffle(pairs)
    pairs = pairs[:N_PAIRS]
    with open(HERE / "pairs.jsonl", "w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")
    lift = sorted(p["ctr_winner"] / p["ctr_loser"] - 1 for p in pairs)
    print(f"{len(tests)} tests, kept {len(pairs)} pairs, median relative CTR lift {lift[len(lift) // 2]:.0%}")


if __name__ == "__main__":
    main()
