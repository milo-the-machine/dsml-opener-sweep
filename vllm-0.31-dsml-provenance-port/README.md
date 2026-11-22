# DSML token provenance for stock vLLM v0.31.0 (DeepSeek V4.1), as a bind-mount overlay

This overlay makes DSML tool-call structure count only where the model wrote the real `｜DSML｜` token (id 128825).
DSML markup typed out in ordinary tokens (in a code block, a quoted example, or reasoning) stays as text. This is
upstream vLLM PR [#65019](https://github.com/vllm-project/vllm/pull/65019) (open, head `cad5796ae967`), adapted to
the v0.31.0 parser API. Christopher Owen ships the same rule in spark-ds41f 1120. It is merged with our rule that
keeps a closer inside a string argument when no structure follows it (spark-ds41f #948 class).

It is live on our GB300 lane (vLLM 0.31.0 + Garner McCloud's dgx-station-recipes overlay) since November 22, 2026,
08:37 CST.

| Check | Before | After |
|---|---|---|
| #876 quoted sample in a code block, tool offered (thinking off / on) | 0/6, 0/6 (real call made) | 6/6, 6/6 |
| #876 no tool offered | 0/6 (content cut at the fence) | 6/6 |
| #948 closers inside an argument | 12/12 | 12/12 |
| #446 call injected in a tool result | 12/12 not obeyed | 12/12 |
| CPU suite in `vllm/vllm-openai:v0.31.0` (`tests/`) | 22/67 (stock) | 67/67 |
| JSON burst (64 concurrent structured outputs) | 64/64 | 64/64 |
| 32-user decode, aggregate tok/s | 3,566–3,664 | 3,622 |

## Files

Seven files are mounted over `/usr/local/lib/python3.12/dist-packages/vllm/`:
- `parser/deepseek_v41.py` replaces our previous overlay.
- `parser/parser_manager.py`.
- `parser/engine/{token_id_scanner,incremental_lexer,streaming_parser_engine,parser_engine,parser_engine_config}.py`.

`DIFFS/` holds each file diffed against stock v0.31.0. For `deepseek_v41.py`, the diff is against our previous
closer overlay.

Dropped from the PR because v0.31.0 lacks the API: the `deepseek_v4` value-extender extraction,
`set_prompt_token_ids`, the prompt-state override, and the docs.

## Switches (environment, no rebuild)
- `VLLM_DSV41_DSML_TOKEN_PROVENANCE=0` turns the rule off and restores the old text behaviour. This is the rollback.
- `VLLM_DSV41_STRUCTURAL_DSML=0` turns our closer rule off.
- `VLLM_DSV41_KEEP_OPEN_ARGS=0` drops an unterminated trailing argument.

At startup the log shows `dsv41-token-origin-structural-v2: DSML token provenance active (atom id 128825, ...)`.

## Test
```bash
OVERLAY_1017=/path/to/dgx-station-recipes/docker/overlay-1017/vllm RUN_SWITCH_MATRIX=1 bash run-tests-in-image.sh
```
The tests are CPU-only, need no GPU or network, and start one pytest container that exits. With the rule switched
off, the old bugs come back on purpose (33 failures).

One behaviour change worth knowing: a real `calls` opener followed by no `invoke` line used to make the parser drop
the rest of the reply silently. Now that text is kept as content.

Port: a DeepSeek-V4.1-Flash subagent (desk work: merge, tests, diffs) driven by Milo (claude-opus-5-5), which ran the in-image
tests, fixed one test fixture, and promoted it on the lane. The overlay files are modified vLLM sources and stay under
vLLM's Apache-2.0 license; the tests and scripts here are MIT like the rest of the repo.
