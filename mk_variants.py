#!/usr/bin/env python3
"""Derive mitigation/dose variants from sessions/poisoned-<d>.json.

poisoned1-<d>  : only ONE broken turn (+ "continue")              -> dose response
strip-<d>      : both broken turns kept, but their DSML tail removed (sentence only)  -> client/server strips markup
drop-<d>       : broken turns and their "continue"s dropped entirely (== clean history + one "continue")
"""
import json, re, sys

depths = [int(x) for x in sys.argv[1].split(",")]
for d in depths:
    s = json.load(open(f"sessions/poisoned-{d}.json"))
    m = s["messages"]
    clean, tail = m[:-4], m[-4:]
    broken_a, cont = tail[0], tail[1]
    v = {}
    v["poisoned1"] = clean + [broken_a, cont]
    strip = lambda a: {**a, "content": re.split(r"\n\n<", a["content"])[0]}
    v["strip"] = clean + [strip(tail[0]), tail[1], strip(tail[2]), tail[3]]
    v["drop"] = clean + [{"role": "user", "content": "continue"}]
    for k, msgs in v.items():
        json.dump({**s, "messages": msgs, "variant": k}, open(f"sessions/{k}-{d}.json", "w"))
    print(d, {k: len(x) for k, x in v.items()}, repr(v["strip"][-4]["content"]))
