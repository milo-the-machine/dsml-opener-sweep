#!/usr/bin/env python3
"""More variants derived from poisoned-<d>.json / clean-<d>.json.

poisonedfar-<d> : broken turns, then the 3 normal tool turns that follow in the longest session (9-15K tokens), then the
                  final failing test  -> broken text is far outside the last 128 tokens
repair-<d>      : each broken turn rewritten as a real bash tool call + tool result "[not executed: ...malformed...]"
usage: mk_more_variants.py 200000,400000,598000  (needs sessions/clean-<max>.json from build_sessions.py; default 800000)
"""
import json, re, sys
depths = [int(x) for x in sys.argv[1].split(",")]
longest = int(sys.argv[2]) if len(sys.argv) > 2 else 800000
big = json.load(open(f"sessions/clean-{longest}.json"))["messages"]
for d in depths:
    s = json.load(open(f"sessions/poisoned-{d}.json")); m = s["messages"]
    clean, ptail = m[:-4], m[-4:]
    head, final = clean[:-2], clean[-2:]
    extra = big[len(head):len(head) + 6]
    if d < longest:
        assert [x["role"] for x in extra] == ["assistant", "tool"] * 3
        json.dump({**s, "messages": head + ptail + extra + final, "variant": "poisonedfar"}, open(f"sessions/poisonedfar-{d}.json", "w"))
    def rep(a, i):
        cmd = re.search(r'string="true">(.*?)</\uff5cDSML\uff5c parameter>', a["content"], re.S).group(1)
        cid = f"call_rep_{i}"
        return [{"role": "assistant", "content": a["content"].split("\n\n<")[0], "reasoning_content": a["reasoning_content"],
                 "tool_calls": [{"id": cid, "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": cmd})}}]},
                {"role": "tool", "tool_call_id": cid, "content": "[not executed: this tool call was malformed in the original reply (missing opener) and was not run]"}]
    json.dump({**s, "messages": clean + rep(ptail[0], 1) + [ptail[1]] + rep(ptail[2], 2) + [ptail[3]], "variant": "repair"},
              open(f"sessions/repair-{d}.json", "w"))
    print(d, "ok")
