#!/usr/bin/env python3
"""Build a synthetic long coding-agent session for the DSML missing-opener sweep.

Shareable: history is made only from public vLLM v0.31.0 source files plus real
`grep`/`wc` output computed over that tree. Deterministic (seeded).

Output: sessions/<variant>-<depth>.json  ->  {"messages": [...], "tools": [...], "approx_tokens": N}
Token counts are measured with a vLLM /tokenize endpoint (chat form, tools included).

usage: build_sessions.py --src <vllm tree> --tokenize-root http://host:port --model <id>
"""
import argparse, json, os, random, re, subprocess, urllib.request

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command in /repo and return stdout+stderr.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The command to run."}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file from the repository.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write (overwrite) a text file in the repository.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
]

SYSTEM = ("You are an autonomous coding agent working in /repo, a checkout of the vLLM inference engine. "
          "You act only through the tools provided. Work step by step: inspect, form a hypothesis, change code, "
          "and verify by running the tests. Keep replies to the user short; do the work with tool calls.")
USER_TASK = ("tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption started failing after the last rebase. "
             "Find the root cause and fix it. Work autonomously with the tools until the test passes; don't ask me questions.")

PYTEST_FAIL = """============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.3.4, pluggy-1.5.0
rootdir: /repo
configfile: pyproject.toml
collected 1 item

tests/v1/core/test_scheduler.py F                                        [100%]

=================================== FAILURES ===================================
____________________ test_chunked_prefill_preemption ___________________________

    def test_chunked_prefill_preemption():
        scheduler = create_scheduler(max_num_batched_tokens=64, num_blocks=11)
        requests = create_requests(num_requests=2, num_tokens=80)
        for request in requests:
            scheduler.add_request(request)
        output = scheduler.schedule()
>       assert len(output.scheduled_new_reqs) == 2
E       AssertionError: assert 1 == 2
E        +  where 1 = len([NewRequestData(req_id='0', prompt_token_ids_len=80, ...)])

tests/v1/core/test_scheduler.py:{line}: AssertionError
=========================== short test summary info ============================
FAILED tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption - AssertionError: assert 1 == 2
============================== 1 failed in {secs}s ==============================="""

SENTENCES_READ = ["Let me look at {p}.", "Reading {p} to see how this path is wired.", "Checking {p} next.",
                  "{p} is on the call path; reading it.", "Opening {p} for the relevant logic."]
SENTENCES_GREP = ["Searching for `{q}` across the tree.", "Let me find where `{q}` is used.", "Grepping for `{q}`."]
SENTENCES_TEST = ["Running the failing test again.", "Re-running the test to check the current state."]
REASON_READ = ["The failure is in admission of new requests under a small token budget, so I need to see how {p} handles it.",
               "{p} might decide how many tokens a new request gets; checking before changing anything.",
               "I haven't ruled out {p} yet. Reading it."]
REASON_GREP = ["I want every call site of `{q}` before I touch it.", "Need to know who else depends on `{q}`."]


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def count_chat(root, model, messages):
    return post(root + "/tokenize", {"model": model, "messages": messages, "tools": TOOLS})["count"]


def count_text(root, model, text):
    return post(root + "/tokenize", {"model": model, "prompt": text, "add_special_tokens": False})["count"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--tokenize-root", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--depths", default="4000,64000,200000,400000,598000,800000")
    ap.add_argument("--out", default="sessions")
    ap.add_argument("--seed", type=int, default=20261122)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    depths = [int(x) for x in a.depths.split(",")]
    target = int(max(depths) * 1.05) + 8000
    src = os.path.abspath(a.src)
    repo_root = os.path.dirname(src)  # files shown as vllm/...
    files = []
    for dp, _, fs in os.walk(src):
        for f in fs:
            if f.endswith(".py"):
                p = os.path.join(dp, f)
                sz = os.path.getsize(p)
                if 1500 < sz < 40000:
                    files.append(os.path.relpath(p, repo_root))
    files.sort()
    rng.shuffle(files)
    idents = sorted({m for f in files[:400] for m in re.findall(r"def ([a-z_]{8,30})\(", open(os.path.join(repo_root, f), errors="ignore").read())})

    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER_TASK}]
    call_n = 0

    def add_call(sentence, reasoning, name, args, result):
        nonlocal call_n
        call_n += 1
        cid = f"call_{call_n:05d}"
        msgs.append({"role": "assistant", "content": sentence, "reasoning_content": reasoning,
                     "tool_calls": [{"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]})
        msgs.append({"role": "tool", "tool_call_id": cid, "content": result})

    # first: run the test
    add_call(SENTENCES_TEST[0], "Start by reproducing the failure.", "bash",
             {"command": "cd /repo && python -m pytest tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption -x -q"},
             PYTEST_FAIL.format(line=rng.randint(400, 1400), secs=f"{rng.uniform(2, 9):.2f}"))
    total = count_chat(a.tokenize_root, a.model, msgs)
    est = total
    cut_points = []  # (index_after_tool_msg, est_tokens)
    fi = 0
    while est < target:
        kind = rng.random()
        if kind < 0.70:
            p = files[fi]; fi += 1
            body = open(os.path.join(repo_root, p), errors="ignore").read()
            res = body[:24000]
            add_call(rng.choice(SENTENCES_READ).format(p=p), rng.choice(REASON_READ).format(p=p), "read_file", {"path": p}, res)
        elif kind < 0.88:
            q = rng.choice(idents)
            out = subprocess.run(["grep", "-rn", "--include=*.py", q, "vllm"], cwd=repo_root, capture_output=True, text=True).stdout
            out = "\n".join(out.splitlines()[:60]) or "(no matches)"
            add_call(rng.choice(SENTENCES_GREP).format(q=q), rng.choice(REASON_GREP).format(q=q), "bash",
                     {"command": f"cd /repo && grep -rn --include=*.py {q} vllm | head -60"}, out)
        elif kind < 0.95:
            p = files[fi]; fi += 1
            body = open(os.path.join(repo_root, p), errors="ignore").read()[:6000]
            add_call(f"Trying a change in {p}.", "Small experimental edit; I will re-run the test after.", "write_file",
                     {"path": p, "content": body}, f"Wrote {len(body)} bytes to {p}")
        else:
            add_call(rng.choice(SENTENCES_TEST), "Check whether the last change moved anything.", "bash",
                     {"command": "cd /repo && python -m pytest tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption -x -q"},
                     PYTEST_FAIL.format(line=rng.randint(400, 1400), secs=f"{rng.uniform(2, 9):.2f}"))
        # incremental estimate: tokens of the two new messages' text + overhead
        a_msg, t_msg = msgs[-2], msgs[-1]
        est += count_text(a.tokenize_root, a.model, a_msg["content"] + a_msg["reasoning_content"] + a_msg["tool_calls"][0]["function"]["arguments"] + t_msg["content"]) + 60
        cut_points.append((len(msgs), est))
    # final turn of every cut: a failing test run so the next natural action is a tool call
    os.makedirs(a.out, exist_ok=True)
    for d in depths:
        goal = d
        for _ in range(4):  # correct the incremental estimate against a real chat-form count
            idx = min(cut_points, key=lambda c: abs(c[1] - goal))[0]
            real = count_chat(a.tokenize_root, a.model, msgs[:idx])
            if abs(real - d) <= max(1500, d * 0.004):
                break
            goal = goal * d / real
        base = msgs[:idx]
        add = []
        cid = "call_final"
        add.append({"role": "assistant", "content": SENTENCES_TEST[1], "reasoning_content": "Check the state before the next step.",
                    "tool_calls": [{"id": cid, "type": "function", "function": {"name": "bash", "arguments": json.dumps(
                        {"command": "cd /repo && python -m pytest tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption -x -q"})}}]})
        add.append({"role": "tool", "tool_call_id": cid, "content": PYTEST_FAIL.format(line=812, secs="4.31")})
        clean = base + add
        n = count_chat(a.tokenize_root, a.model, clean)
        json.dump({"messages": clean, "tools": TOOLS, "tokens": n, "depth_target": d, "variant": "clean"},
                  open(f"{a.out}/clean-{d}.json", "w"))
        broken = ("Let me run the failing test again with full output.\n\n"
                  "<｜DSML｜ parameter name=\"command\" string=\"true\">cd /repo && python -m pytest "
                  "tests/v1/core/test_scheduler.py::test_chunked_prefill_preemption -x -q 2>&1 | tail -40</｜DSML｜ parameter>\n"
                  "</｜DSML｜ invoke>\n</｜DSML｜ calls>")
        pois = clean + [{"role": "assistant", "content": broken, "reasoning_content": "The test still fails; run it again with more output."},
                        {"role": "user", "content": "continue"},
                        {"role": "assistant", "content": broken, "reasoning_content": "Run the test with full output."},
                        {"role": "user", "content": "continue"}]
        n2 = count_chat(a.tokenize_root, a.model, pois)
        json.dump({"messages": pois, "tools": TOOLS, "tokens": n2, "depth_target": d, "variant": "poisoned"},
                  open(f"{a.out}/poisoned-{d}.json", "w"))
        print(f"depth {d}: clean {n} tokens ({len(clean)} msgs), poisoned {n2}", flush=True)


if __name__ == "__main__":
    main()
