#!/usr/bin/env python3
"""Final tables for the report: variant x engine (all depths), depth bands, failure shapes. Wilson 95% CIs."""
import collections, glob, gzip, json, math

DS = 128825
BROKEN_CMD = "python -m pytest tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption -x -q 2>&1 | tail -40"
rows = []
for p in sorted(glob.glob("results/sweep-*.jsonl")) + sorted(glob.glob("results/sweep-*.jsonl.gz")):
    rows += [json.loads(l) for l in (gzip.open(p, "rt") if p.endswith(".gz") else open(p))]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0, (c - h) / d) * 100, min(1, (c + h) / d) * 100)


def is_dsml_fail(r):
    """failure attributable to tool-call formatting (exclude honest give-up prose)"""
    if r["class"] == "CALL_OK":
        return False
    c = r["out"]["content"] or ""
    t = r["out"].get("token_ids") or []
    if r["class"] in ("ORPHAN_MARKUP", "MARKUP_WITH_OPENER", "CALL_BAD_SHAPE", "CALL_BAD_JSON", "EMPTY"):
        return True
    # TEXT_ONLY: count as DSML failure only if output tokens hold DSML structure (swallowed) or the reply is a short
    # one-liner that announces a tool action (imitating text-only turns)
    if DS in t or "<｜DSML｜" in c or "｜DS" in c:
        return True
    return len(c) < 200


def shape(r):
    c = r["out"]["content"] or ""
    t = r["out"].get("token_ids")
    eng = r["engine"]
    if r["class"] == "ORPHAN_MARKUP":
        s = "A: params+closers as text, no opener/invoke" + (" (verbatim copy)" if BROKEN_CMD in c else " (new command)")
        if t is not None:
            s += f", real-token DSML in output: {t.count(DS)}"
        return s
    if r["class"] == "TEXT_ONLY" and t and DS in t:
        return "B: real <calls> opener, invoke line missing -> parser drops the call body, client gets the sentence only"
    if r["class"] == "TEXT_ONLY":
        return "C: text-only (" + ("short tool-announcing line" if len(c) < 200 else "long prose / give-up") + ")"
    return r["class"]


def tbl(keyf, filt=lambda r: True, title=""):
    agg = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        if not filt(r):
            continue
        k = keyf(r)
        agg[k][0] += 1
        agg[k][1] += is_dsml_fail(r)
    print(f"\n### {title}\n")
    print("| key | n | tool-call failures | rate | 95% CI |")
    print("|---|---:|---:|---:|---|")
    for k in sorted(agg):
        n, f = agg[k]
        lo, hi = wilson(f, n)
        print(f"| {' / '.join(map(str, k))} | {n} | {f} | {100*f/n:.1f}% | {lo:.1f}–{hi:.1f}% |")


tbl(lambda r: (r["variant"], r.get("effort", "high"), r["engine"]), title="variant x engine (all depths)")
tbl(lambda r: (r["variant"], r.get("effort", "high")), title="variant pooled over engines (all depths)")
band = lambda d: "4K-64K" if d <= 64000 else "200K-800K"
tbl(lambda r: (r["variant"], band(r["depth"]), r["engine"]), filt=lambda r: r["variant"] in ("poisoned", "clean") and r.get("effort", "high") == "high",
    title="poisoned/clean by depth band")
tbl(lambda r: (r["variant"], f"{r['depth']//1000}K"), filt=lambda r: r["variant"] in ("poisoned", "poisonedfar") and r["depth"] in (200000, 400000, 598000) and r.get("effort", "high") == "high",
    title="poisoned (broken turns in last ~200 tokens) vs poisonedfar (9-15K tokens of normal turns after them), same depths, pooled")
print("\n### failure shapes (all variants)\n")
sh = collections.Counter()
by = collections.defaultdict(collections.Counter)
for r in rows:
    if is_dsml_fail(r):
        sh[shape(r)] += 1
        by[shape(r)][r["engine"]] += 1
for s, n in sh.most_common():
    print(f"- {n} × {s}  ({dict(by[s])})")
print("\nexcluded as not tool-format failures (honest give-up prose):",
      sum(1 for r in rows if r["class"] != "CALL_OK" and not is_dsml_fail(r)))
print("total requests:", len(rows), " engines:", dict(collections.Counter(r["engine"] for r in rows)))
