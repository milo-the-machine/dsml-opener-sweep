# DSML missing-opener: three-engine test for Christopher Owen (2026-11-22)

Question (Owen, X, 2026-11-22): at 598K tokens a coding agent got a bash call with its first two lines missing
(no `calls` opener, no `invoke name=`), only the parameter and closing tags, as plain text. Twice in a row.
Owen asked whether the model or the stack drops the opener, whether it happens at 4K, and which of three fixes to take.

## Bottom line

1. **We could not reproduce the first occurrence.** With a clean history: **0 of 600** requests at 4K–800K on three
   engines, at effort high and max. Spelled DSML in the history's tool results (encoding docs and fixtures) did
   not trigger it either (0/528 + 1/528, and that one was a parser bug, see §4).
2. **The self-feeding loop reproduces, and it comes from the model, not from his stack.** Two broken turns in
   the history (the exact Herlon shape, encoded as plain text as fix 1 does) make the model write more of
   them, on **all three engines**: spark-ds41f 1120 (copy drafts on), stock vLLM 0.31 + Garner kernels on GB300 (no
   copy drafts), and knapcio SGLang v2.5. Pooled over engines, 2.4% at effort high (37/1,560) and 7.3% at
   effort max (7/96). With a clean history the rate is 0%.
3. **It is worse at depth but not limited to it.** Poisoned at 200K–800K: 6.1% / 4.2% / 1.0% (GB300 / 1120 /
   SGLang). At 4K–64K: 0.4% / 0.4% / 0.0% (1/252, 1/252, 0/144). So it can happen at 4K, at about a tenth of the
   long-context rate.
4. **The last 128 tokens are not required.** With 9–15K tokens of normal tool turns after the broken turns, the
   rate drops from 3.5% to 0.7% (pooled, same depths) but does not reach 0. Imitation reaches past the sliding
   window. Having the broken text in the window amplifies it; it is not the only route.
5. **Keeping the broken turn out of history fixes it in our data. Stripping the markup does not.**
   - drop (broken turns removed): **0/576**.
   - repair (broken turns rewritten as real tool calls with a "not executed" tool result): **0/456**.
   - strip (sentence kept, DSML tail removed): **22/576 = 3.8%**. The model now imitates turns that announce a
     tool action and make no call ("Let me run the failing test again." followed by nothing).
   - One broken turn instead of two: 1.2% vs 2.4%. The effect grows with the number of broken turns.
6. **Every failure is missing the `invoke name=` line, and the parameter tags are written in ordinary tokens.**
   Shapes, with token IDs (vLLM engines, `return_token_ids`):
   - **A (45×)**: one sentence, then `<｜DSML｜ parameter …>…</｜DSML｜ parameter></｜DSML｜ invoke></｜DSML｜ calls>`
     as text with no opener and no invoke line. This is Herlon's symptom. In 34 the command is new; 11 are
     verbatim copies of the broken turn. In all 42 that carry token IDs (SGLang returns none), the parameter
     tags are ordinary pieces (`｜`,`DS`,`ML`,`｜`). 39 of the 42 contain no real 128825 at all, and 3 switch to the
     real token for the last two closers only.
   - **B (7×, GB300 and 1120)**: a **real** `<｜DSML｜ calls>` opener (token 128825), then no invoke line and a
     spelled parameter. Both parsers enter the call, cannot build one without a tool name, and **drop the
     body silently**. The client gets only the sentence (`"Let me inspect … properly.\n\n"`), with `finish_reason`
     `stop` and no error. On 1120 this is the "no path from inside a call back to reply text" property in action.
   - **C (24×)**: a short tool-announcing line with no call. Mostly in the strip arm.
   - The model often notices the problem in its reasoning ("my previous tool call had malformed tags (fullwidth
     characters)") and still repeats the broken format.
7. **The loop does not depend on spec decode or copy drafts.** GB300 runs DSpark k≤5 with no copy drafts.
   SGLang is a different engine with a different parser. Both show the same shapes. The 1120 logs show no
   loop-detector events and no errors during the runs.

## What this means for his three options

- **Accept a call with no opener:** not safe. In all 42 A-shape cases with token IDs, the parameter tags are
  ordinary tokens, and 39 have no real DSML token anywhere. Accepting them means accepting spelled structure,
  which is bug 3 again. His instinct is
  right. A narrower rule ("real-token closers, parameters match exactly one tool") would have rescued only the
  3 mixed cases.
- **Keep a broken turn out of history:** this is the one that works in our data (drop 0/576, repair 0/456).
  Two caveats:
  1. Don't do it by stripping the markup. Strip leaves "announced but didn't call" turns, and the model imitates those (3.8%).
  2. The server can't edit the client's history, but it can stop producing these turns. When a reply
     contains DSML structure that doesn't parse (shape B's real opener, or shape A's spelled tail when tools
     were offered), don't return it as plain text with `finish_reason: stop`. Either resample it on the
     server or return an error, so the client never saves it. Shape B is a server-side detection with
     no ambiguity, because the real token is there. A render-time rewrite of a history turn into a real call
     (our repair arm) also worked, but it changes what the client sent, which is the riskier policy.
- **Grammar to hold the opener:** our data says the minimal grammar has to enforce
  `calls` → `invoke name=` → `parameter`, not just the opener. In shape B the opener was there and the invoke
  line was missing. If it only allows 128825 inside an open call, it misses that.

## Engines (all live, same day, same sampling: T=1.0, top_p=1.0, thinking on, `reasoning_effort` high unless stated)

| engine | where | weights | tool parser | spec decode |
|---|---|---|---|---|
| owen1120 | 4× DGX Spark (5–8), TP4, `spark-ds41f:candidate-62` (= release 1120), his `tp4-switched` shape, untouched | base 1017 (shard-10 sha 835e9a8b…, same as spark1) | his deepseek_v41 with token provenance (fix 5) | DSpark k=5 + adaptive verification, copy drafts on (log) |
| gb300 | 1× GB300 + RTX PRO 6000 sidecar, vLLM v0.31.0 + Garner McCloud overlay + our patches (Pg64) | stock 1017 | stock v0.31 deepseek_v41 + our closer overlay (text-based, no provenance) | DSpark k≤5, no copy drafts |
| sglang | 4× DGX Spark (1–4), knapcio dsv41-4x-spark v2.5 (`canary-roce-v25-vision`) | base 1017 | knapcio/SGLang deepseek_v41 | DSpark (knapcio) |

All three render the poisoned history to the same token count (+197 over clean). The spelled markup in user text,
assistant history and tool results stays plain text on all three (fix 1 present everywhere, checked with `/tokenize`).

## Harness (shareable; built only from public vLLM v0.31.0 source + public DeepSeek encoding fixtures)

- `build_sessions.py`: a coding agent session (system + one user task + N `read_file`/`grep`/`write_file`/`pytest`
  turns with `reasoning_content`; tool results are real files and real `grep` output from the vLLM tree) cut at
  4K/64K/200K/400K/598K/800K. Each history ends with a failing `pytest`, so the natural next action is a tool call.
  Measured prompt tokens: 3,095 / 67,161 / 200,748 / 406,022 / 604,410 / 812,321.
- Variants: `clean`; `poisoned` (+ two broken assistant turns, Herlon shape, each followed by user `continue`);
  `poisoned1` (one broken turn); `poisonedfar` (broken turns then 3 normal tool turns, 9–15K tokens);
  `strip`; `drop`; `repair`; `dsmlctx` (6 reads of DSML-heavy DeepSeek encoding docs in the last 30%);
  `dsmltail` (last tool result = a DSML encoding fixture).
- `run.py probe|sweep`: OpenAI-compatible, stdlib only, alternates stream / non-stream, keeps raw content,
  reasoning and token IDs per request (`results/*.jsonl`). `final_tables.py` produces the tables below.

## Short probes (Owen's earlier bugs), n=6 per row per engine, half streaming

| case | gb300 | owen1120 | sglang |
|---|---|---|---|
| #876 quote DSML in a code block, tool offered, thinking off | **6/6 real call made** (bug 3) | 6/6 pass | **6/6 real call made** |
| same, thinking on | **6/6 call** | 6/6 pass | **6/6 call** |
| #876 no tool offered | **6/6 content cut at the code fence** | 6/6 pass | 6/6 pass |
| #948 DSML closers inside a write_file argument | 12/12 intact | 12/12 intact | 12/12 intact |
| #446 DSML call injected in a tool result | 12/12 not obeyed | 12/12 not obeyed | 12/12 not obeyed |

SGLang token pieces for the #876 failure (logprobs): the model wrote `｜`,`DS`,`ML`,`｜` inside a ```` ```markdown ```` fence and
ended with FINISHED. The parser still produced `get_weather(Boston)`. GB300 and SGLang both have Owen's bug 3. Only 1120 has fix 5.

## Sweep tables

See `FINAL-TABLES.md` (6,168 requests: gb300 2,376, owen1120 2,376, sglang 1,416). Headline rows:

| variant | n (3 engines) | no valid tool call | 95% CI |
|---|---:|---:|---|
| clean, effort high | 504 | 0 | 0–0.8% |
| clean, effort max | 96 | 0 | 0–3.8% |
| dsmlctx | 528 | 0 | 0–0.7% |
| dsmltail | 528 | 1 (GB300 parser bug, below) | 0–1.1% |
| poisoned, high | 1,560 | 37 (2.4%) | 1.7–3.3% |
| poisoned, max | 96 | 7 (7.3%) | 3.6–14.3% |
| poisoned1 | 576 | 7 (1.2%) | 0.6–2.5% |
| poisonedfar | 672 | 5 (0.7%) | 0.3–1.7% |
| strip | 576 | 22 (3.8%) | 2.5–5.7% |
| drop | 576 | 0 | 0–0.7% |
| repair | 456 | 0 | 0–0.8% |

Excluded from failures: 4 long, honest give-up replies ("I wasn't able to fix this one…") in the dsmltail arm.

## Side findings

- **GB300, ours:** bug 3 (#876) is live on our lane, both with and without tools. Separately, in one dsmltail
  streaming reply, reasoning that quoted the DSML format ("I'll follow the reference format exactly: `<｜DSML｜ …`")
  was parsed as structure. That produced a tool call named `"..."` whose argument held the reasoning text. A
  text-based parser has no defence against either. Port the token-provenance rule (Owen 1120 / vLLM #65019) to
  the GB300 overlay.
- **SGLang knapcio v2.5:** bug 3 present with tools offered (6/6 + 6/6). Worth reporting to knapcio.
- **1120 oddities (1 each, not reproduced):** at 800K, poisoned, streaming: the reply was `"\n\n"` + shape B. At
  800K, strip, streaming: the whole reply was 2 tokens, `Let` in reasoning and then EOS inside thinking.
- **SGLang's poisoned rate is lower** (0.7% vs 2.5–3.5%, overlapping CIs at the low end). Cause not investigated.
  The prompt token counts match the vLLM engines to within 8 tokens.

## Limits

- The history is synthetic. Herlon's real transcript may contain whatever started his first occurrence
  (client-side history rewriting, compaction, earlier turns that quote markup). We tested two plausible
  triggers (DSML in tool results, near and far) and neither produced the first occurrence.
- One prompt family, one task. Rates are per-request on near-identical prompts, not independent sessions.
- SGLang returns no token IDs, so its shapes are classified from text only.
- We did not test a server-side grammar or resample, because those need engine changes.

Receipts: `results/{probe,sweep}-*.jsonl`, logs `sweep-*.log`, sessions `sessions/*.json` (regenerable with the build script).
