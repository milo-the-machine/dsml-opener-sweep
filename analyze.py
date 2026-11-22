#!/usr/bin/env python3
"""Aggregate results/sweep-*.jsonl -> table + failure catalogue (markdown to stdout)."""
import collections, glob, gzip, json, re, sys

BROKEN_CMD = "python -m pytest tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption -x -q 2>&1 | tail -40"
DS = 128825
tags = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else None
rows = []
for p in sorted(glob.glob("results/sweep-*.jsonl")) + sorted(glob.glob("results/sweep-*.jsonl.gz")):
    for l in (gzip.open(p, "rt") if p.endswith(".gz") else open(p)):
        r = json.loads(l)
        if tags and r.get("tag") not in tags:
            continue
        rows.append(r)


def sub(r):
    """failure subtype"""
    c = r["out"]["content"] or ""
    t = r["out"].get("token_ids")
    if r["class"] == "CALL_OK":
        return "ok"
    copy = BROKEN_CMD in c
    real = (t or []).count(DS) if t else None
    if r["class"] == "ORPHAN_MARKUP":
        kind = "copy" if copy else "new"
        return f"orphan-{kind}" + ("" if real is None else f"-real{real}")
    if r["class"] == "TEXT_ONLY":
        return "textonly" + ("" if real is None else f"-real{real}")
    return r["class"].lower()


agg = collections.defaultdict(collections.Counter)
for r in rows:
    k = (r["engine"], r["variant"], r.get("effort", "high"), r["depth"])
    agg[k]["n"] += 1
    agg[k][sub(r)] += 1
    agg[k]["fail"] += r["class"] != "CALL_OK"

print("| engine | variant | effort | depth (target) | n | no tool call | rate | breakdown |")
print("|---|---|---|---:|---:|---:|---:|---|")
for k in sorted(agg, key=lambda k: (k[1], k[0], k[2], k[3])):
    c = agg[k]
    br = ", ".join(f"{s} {v}" for s, v in sorted(c.items()) if s not in ("n", "fail", "ok"))
    print(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]:,} | {c['n']} | {c['fail']} | {100*c['fail']/c['n']:.1f}% | {br} |")

# pooled per variant x engine
print()
pool = collections.defaultdict(collections.Counter)
for r in rows:
    pool[(r["variant"], r["engine"], r.get("effort", "high"))]["n"] += 1
    pool[(r["variant"], r["engine"], r.get("effort", "high"))]["f"] += r["class"] != "CALL_OK"
print("| variant | engine | effort | n | no tool call |")
print("|---|---|---|---:|---:|")
for k in sorted(pool):
    print(f"| {k[0]} | {k[1]} | {k[2]} | {pool[k]['n']} | {pool[k]['f']} ({100*pool[k]['f']/pool[k]['n']:.1f}%) |")
