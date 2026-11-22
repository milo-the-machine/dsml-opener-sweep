# dsml-opener-sweep

This is a test harness and dataset for a DeepSeek-V4.1 tool-call failure, plus our results. In long agent
sessions the model sometimes writes a tool call with its first lines missing: no `<｜DSML｜ calls>` opener and no
`invoke name=`, just the parameter and closing tags, which the client receives as plain text. We ran it on three
serving stacks on the same day.

Christopher Owen reported this ([spark-ds41f](https://github.com/christopherowen/spark-ds41f), X post 2026-11-22),
using a transcript from a coding-agent user (Herlon) at 598K tokens. This repo answers three of his open questions
with measurements: is it the model or the stack, does it happen at 4K, and which mitigation works.

Full write-up: [REPORT.md](REPORT.md). All tables: [FINAL-TABLES.md](FINAL-TABLES.md). Every failure with
token IDs and decoded token pieces: [`results/failures.jsonl`](results/failures.jsonl).

## Findings (6,168 requests, 2026-11-22)

| Question | Answer |
|---|---|
| Does a clean history produce the missing opener? | We could not make it happen: **0 / 600** at 4K–800K on three engines, effort high and max. |
| Is the self-feeding loop the model or the stack? | **The model.** Two broken turns in the history (encoded as plain text) make the model write more of them on **all three** stacks: spark-ds41f 1120, stock vLLM 0.31 on GB300 (no copy drafts), and SGLang (knapcio v2.5). Pooled 2.4% at effort high, 7.3% at max. |
| Does it happen at 4K? | Yes, but rarely. Poisoned 4K–64K: 0.4% / 0.4% / 0.0%. At 200K–800K: 6.1% / 4.2% / 1.0%. |
| Does it need the last 128 tokens? | No. With 9–15K tokens of normal turns after the broken turns, the rate drops (3.5% → 0.7%) but does not reach 0. |
| What fixes it? | Keep the broken turn out of history: **drop 0/576**, **rewrite as a real call + "not executed" result 0/456**. Stripping the markup does *not* work (3.8%): the model then copies "announced a tool, made no call" turns. |
| What do the failures look like? | Every one is missing the `invoke name=` line. The parameter tags are written as ordinary tokens (`｜`,`DS`,`ML`,`｜`) in all 42 cases that carry token IDs. A second shape: a real-token `calls` opener followed by no invoke line. Both vLLM parsers drop the body silently and the client gets only the sentence, `finish_reason: stop`. |

Short probes for older bugs (#876 quoted markup becomes a call, #948 closers inside arguments, #446 injection via
tool result): spark-ds41f 1120 passes all of them. Stock vLLM 0.31 (+ our closer overlay, before the port below) and SGLang knapcio v2.5
both turn a quoted, ordinary-token DSML sample in a code block into a real call when a tool is offered (12/12 each).

## Also here

[`vllm-0.31-dsml-provenance-port/`](vllm-0.31-dsml-provenance-port/): the real-token rule (vLLM PR #65019) ported to stock
vLLM v0.31.0 as a bind-mount overlay, live on our GB300 lane since November 22. The sweep numbers above were measured before it.

## Rules for agents running this

1. Use the engine's own `/tokenize` for session sizes (`build_sessions.py --tokenize-root`), not a local tokenizer.
   **Check:** the build log's measured counts land within ~1% of the targets.
2. Run the cells in ascending depth. The sessions are nested prefixes, so every cell after the first is mostly a
   prefix-cache hit. **Check:** `prompt_tokens_details.cached_tokens` is close to `prompt_tokens` from the second request on.
3. Treat a failure as a tool-format failure only from content and token IDs. Long "I could not fix this" replies are
   excluded (4 in our data). **Check:** `final_tables.py` prints the exclusion count.
4. Do not compare engines on one rep. Rates are 1–7%, so use ≥48 reps per cell per variant.

## Steps

```bash
# 1. sessions (needs a vLLM v0.31.0 source tree for file contents, and any DSV4.1 vLLM endpoint for /tokenize)
python3 build_sessions.py --src /path/to/vllm-v0.31.0/vllm \
  --tokenize-root http://HOST:PORT --model MODEL_ID
python3 mk_variants.py 4000,64000,200000,400000,598000,800000      # poisoned1, strip, drop
python3 mk_more_variants.py 200000,400000,598000                    # poisonedfar, repair
DSV41_ENCODING_DIR=/path/to/DeepSeek-V4.1-Flash-1017/inference/encoding \
  python3 mk_dsml_variants.py 4000,200000,400000,598000,800000      # dsmlctx, dsmltail

# 2. probes (2 min) and sweep
python3 run.py probe --engine a=http://HOST_A:PORT/v1 --engine b=http://HOST_B:PORT/v1 --n 6
python3 run.py sweep --engine a=http://HOST_A:PORT/v1 --variants clean,poisoned \
  --depths 4000,64000,200000,400000,598000,800000 --reps 48 --conc 8 --tag main
#    SGLang rejects return_token_ids: add  --no-token-ids-for <name>

# 3. tables
python3 final_tables.py
```

Sampling used throughout: `temperature 1.0`, `top_p 1.0`, `chat_template_kwargs.thinking=true`,
`reasoning_effort=high` (or `max`), `max_tokens 8192`, alternating streaming and non-streaming requests.

## What the session is

A coding agent (system prompt + one user task) works through `read_file`, `grep`, `write_file` and `pytest`
turns, each carrying `reasoning_content`. The tool results are real files and real `grep` output from the public
vLLM v0.31.0 tree. Every history ends with a failing test, so the natural next action is a tool call. The "broken
turn" is the Herlon shape verbatim: a sentence, then `<｜DSML｜ parameter …>…</｜DSML｜ parameter></｜DSML｜ invoke></｜DSML｜ calls>`
with no opener and no invoke line, followed by a user `continue`.

## Limits

The history is synthetic. Whatever triggered Herlon's first occurrence may be something we didn't build
(client-side history rewriting, compaction, earlier turns that quote markup). We use one prompt family, and our
reps reuse near-identical prompts, so they are not independent sessions. SGLang returns no token IDs.

## Credits

Christopher Owen (spark-ds41f, the report and the questions). Herlon (the transcript behind it).
joesinvestments, koldfrontier, Acermax and Jordi for the earlier DSML bugs (#876, #948, #446). knapcio
(dsv41-4x-spark SGLang). Garner McCloud (dgx-station-recipes, the GB300 base). Measurements and harness:
Milo (claude-opus-5-5) for James Meadlock. MIT.
