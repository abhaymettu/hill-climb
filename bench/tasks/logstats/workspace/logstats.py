"""Summarize web access logs.

Each input line looks like

    2026-03-01T12:00:03Z 10.0.0.7 alice GET /api/users/42?full=1 200 31ms

with fields: timestamp, ip, user, method, path, status, latency. Fields are separated by runs of
whitespace. A line with a different number of fields, a status that is not an integer, or a latency
that is not an integer followed by "ms" is malformed and is skipped (and counted).

analyze(lines) returns a dict:

    requests      number of well-formed lines
    malformed     number of skipped lines (blank lines are ignored, not counted)
    users         {user: request count}; user names compare case-insensitively (str.casefold) and are
                  reported in their casefolded form
    unique_ips    number of distinct ip strings
    error_rate    share of requests with status >= 500, rounded to 4 places (0.0 when no requests)
    top_paths     the 5 most requested normalized paths as [path, count] pairs, highest count first;
                  ties keep the order in which the paths first appeared in the input
    p95_ms        {normalized path: 95th percentile latency} for every path, using the nearest-rank
                  method: the value at 1-based rank ceil(0.95 * n) of the sorted latencies

A path is normalized by dropping the query string (everything from the first "?"), casefolding it,
replacing every path segment made only of ASCII digits with ":id", and removing one trailing "/"
unless the path is just "/".
"""
import math
import re


def parse_line(line):
    line = line.strip()
    parts = re.split(r"\s+", line)
    if len(parts) != 7:
        return None
    ts, ip, user, method, path, status, latency = parts
    if not re.match(r"^-?\d+$", status):
        return None
    if not re.match(r"^\d+ms$", latency):
        return None
    return {
        "ts": ts,
        "ip": ip,
        "user": user,
        "method": method,
        "path": path,
        "status": int(status),
        "latency": int(latency[:-2]),
    }


def normalize_path(path):
    if "?" in path:
        path = path[: path.index("?")]
    path = path.casefold()
    segments = path.split("/")
    out = []
    for seg in segments:
        if seg != "" and all(c in "0123456789" for c in seg):
            out.append(":id")
        else:
            out.append(seg)
    path = "/".join(out)
    if path.endswith("/") and path != "/":
        path = path[:-1]
    return path


def percentile_nearest_rank(values, pct):
    ordered = []
    for v in values:
        i = 0
        while i < len(ordered) and ordered[i] <= v:
            i += 1
        ordered.insert(i, v)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[max(rank, 1) - 1]


def analyze(lines):
    records = []
    malformed = 0
    for line in lines:
        if line.strip() == "":
            continue
        rec = parse_line(line)
        if rec is None:
            malformed += 1
        else:
            records.append(rec)

    users = {}
    for rec in records:
        name = rec["user"].casefold()
        count = 0
        for other in records:
            if other["user"].casefold() == name:
                count += 1
        users[name] = count

    ips = []
    for rec in records:
        if rec["ip"] not in ips:
            ips.append(rec["ip"])

    errors = 0
    for rec in records:
        if rec["status"] >= 500:
            errors += 1
    error_rate = round(errors / len(records), 4) if records else 0.0

    order = []
    counts = {}
    for rec in records:
        p = normalize_path(rec["path"])
        if p not in counts:
            order.append(p)
            counts[p] = 0
        counts[p] += 1
    ranked = list(order)
    for i in range(len(ranked)):
        for j in range(len(ranked) - 1 - i):
            if counts[ranked[j]] < counts[ranked[j + 1]]:
                ranked[j], ranked[j + 1] = ranked[j + 1], ranked[j]
    top_paths = [[p, counts[p]] for p in ranked[:5]]

    p95 = {}
    for p in order:
        lat = [rec["latency"] for rec in records if normalize_path(rec["path"]) == p]
        p95[p] = percentile_nearest_rank(lat, 95)

    return {
        "requests": len(records),
        "malformed": malformed,
        "users": users,
        "unique_ips": len(ips),
        "error_rate": error_rate,
        "top_paths": top_paths,
        "p95_ms": p95,
    }
