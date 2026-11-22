#!/usr/bin/env python3
"""Variants for the *first-occurrence* hunt (no poisoned assistant turns).

dsmlctx-<d>  : clean-<d> + 6 extra read_file turns of public DeepSeek encoding docs/fixtures (spelled DSML markup
               in tool results), spread over the last 30% of the history
dsmltail-<d> : clean-<d> but the last tool result before the model's turn is one of those files
               (spelled DSML sits inside the final ~1K tokens)
Source files: the DeepSeek-V4.1-Flash-1017 checkpoint's `inference/encoding/` dir (MIT; set DSV41_ENCODING_DIR) (README.md, tests/test_output_{1,3}.txt, encoding.py).
"""
import json, os, sys

E = os.environ.get("DSV41_ENCODING_DIR", "inference/encoding")  # the checkpoint's inference/encoding dir (DeepSeek, MIT)
FILES = ["README.md", "tests/test_output_1.txt", "encoding.py", "tests/test_output_3.txt", "test_encoding.py", "README.md"]
depths = [int(x) for x in sys.argv[1].split(",")]
for d in depths:
    s = json.load(open(f"sessions/clean-{d}.json"))
    m = s["messages"]
    head, tail = m[:-2], m[-2:]
    # positions: assistant indices in last 30% of head
    asst = [i for i, x in enumerate(head) if x["role"] == "assistant"]
    late = [i for i in asst if i > len(head) * 0.7] or asst[-6:]
    picks = [late[int(k * (len(late) - 1) / 5)] for k in range(6)]
    out = []
    n = 0
    for i, x in enumerate(head):
        if i in picks:
            f = FILES[n % len(FILES)]; n += 1
            cid = f"call_dsml_{n}"
            out.append({"role": "assistant", "content": f"Checking how the tokenizer formats tool calls in encoding/{f}.",
                        "reasoning_content": "The scheduler change might interact with the DSML tool-call encoding; read the reference.",
                        "tool_calls": [{"id": cid, "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"path": f"encoding/{f}"})}}]})
            out.append({"role": "tool", "tool_call_id": cid, "content": open(os.path.join(E, f)).read()[:24000]})
        out.append(x)
    json.dump({**s, "messages": out + tail, "variant": "dsmlctx"}, open(f"sessions/dsmlctx-{d}.json", "w"))
    cid = "call_dsml_tail"
    t2 = [{"role": "assistant", "content": "Let me check the reference tool-call encoding fixture before the next run.",
           "reasoning_content": "Look at the fixture to make sure the formatting path is not involved.",
           "tool_calls": [{"id": cid, "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"path": "encoding/tests/test_output_1.txt"})}}]},
          {"role": "tool", "tool_call_id": cid, "content": open(os.path.join(E, "tests/test_output_1.txt")).read()}]
    json.dump({**s, "messages": m + t2, "variant": "dsmltail"}, open(f"sessions/dsmltail-{d}.json", "w"))
    print(d, len(out + tail), len(m + t2))
