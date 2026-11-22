# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the DeepSeek V4.1 DSML token-provenance tests (CPU only).

No HF tokenizer, no torch, no network. The tokenizer below models the two
things the guard depends on:

* the ``｜DSML｜`` atom is an *added* token (id 128825) that is not special,
  whose text is the same as the six ordinary characters that spell it, so
  "spelled with ordinary tokens" and "arrived as the token" produce identical
  text and different ids;
* decoding is context free (one piece per id), so a delta's text can be built
  for any id slice with no detokenizer state.

Token ids follow the lane's tokenizer: 128825 ``｜DSML｜``, 128822
``</think>``, 128821 ``<think>``, 128820 ``<｜begin▁of▁sentence｜>``.
"""

from __future__ import annotations

from typing import Any, Sequence

ATOM = "｜DSML｜"
ATOM_ID = 128825
THINK_START_ID = 128821
THINK_END_ID = 128822
BOS_ID = 128820
THINK_START_TEXT = "<think>"
THINK_END_TEXT = "</think>"
BOS_TEXT = "<｜begin▁of▁sentence｜>"

CALLS_OPEN = "<｜DSML｜ calls>"
CALLS_CLOSE = "</｜DSML｜ calls>"
INVOKE_OPEN = '<｜DSML｜ invoke name="'
INVOKE_CLOSE = "</｜DSML｜ invoke>"
PARAM_OPEN = "<｜DSML｜ parameter"
PARAM_CLOSE = "</｜DSML｜ parameter>"


class FakeTokenizer:
    """Callable stand-in for the DeepSeek V4.1 tokenizer."""

    def __init__(self) -> None:
        self._pieces: dict[int, str] = {
            ATOM_ID: ATOM,
            THINK_START_ID: THINK_START_TEXT,
            THINK_END_ID: THINK_END_TEXT,
            BOS_ID: BOS_TEXT,
        }
        self._vocab: dict[str, int] = {
            ATOM: ATOM_ID,
            THINK_START_TEXT: THINK_START_ID,
            THINK_END_TEXT: THINK_END_ID,
            BOS_TEXT: BOS_ID,
        }
        self._next_id = 1000

    # ── ids ────────────────────────────────────────────────────────────
    def _char_id(self, ch: str) -> int:
        tid = self._vocab.get(ch)
        if tid is None:
            tid = self._next_id
            self._next_id += 1
            self._vocab[ch] = tid
            self._pieces[tid] = ch
        return tid

    def spelled(self, text: str) -> list[int]:
        """Ids that spell *text* with ordinary tokens only."""
        return [self._char_id(ch) for ch in text]

    def genuine(self, text: str) -> list[int]:
        """Ids for *text* where every ``｜DSML｜`` arrives as the DSML token."""
        ids: list[int] = []
        for index, part in enumerate(text.split(ATOM)):
            if index:
                ids.append(ATOM_ID)
            ids.extend(self.spelled(part))
        return ids

    # ── tokenizer protocol ─────────────────────────────────────────────
    def decode(self, token_ids: Sequence[int], *args: Any, **kwargs: Any) -> str:
        return "".join(self._pieces.get(int(tid), "") for tid in token_ids)

    def convert_ids_to_tokens(self, token_id: int) -> str:
        return self._pieces.get(int(token_id), "")

    def convert_tokens_to_ids(self, token: str) -> int | None:
        return self._vocab.get(token)

    def get_vocab(self) -> dict[str, int]:
        return dict(self._vocab)

    def get_added_vocab(self) -> dict[str, int]:
        return {}

    @property
    def all_special_tokens(self) -> list[str]:
        # The DSML atom is an *added* token, not a special token: it is not in
        # all_special_tokens, so the engine's auto-drop never sees it and
        # decode() returns its text. Only the BOS/think markers are special.
        return [BOS_TEXT, THINK_START_TEXT, THINK_END_TEXT]

    @property
    def all_special_ids(self) -> list[int]:
        return [BOS_ID, THINK_START_ID, THINK_END_ID]

    bos_token = BOS_TEXT
    bos_token_id = BOS_ID
    eos_token = BOS_TEXT
    eos_token_id = BOS_ID

    def __call__(self, text: str, add_special_tokens: bool = False) -> list[int]:
        return self.spelled(text)


SCHEDULES = ("nonstream", "one_chunk", "per_token", "lag3")


def deltas_for(tok: FakeTokenizer, ids: Sequence[int], schedule: str):
    """``(delta_text, delta_ids)`` sequence for one schedule."""
    ids = list(ids)
    if schedule == "one_chunk":
        return [(tok.decode(ids), ids)]
    if schedule == "per_token":
        return [(tok.decode([tid]), [tid]) for tid in ids]
    assert schedule == "lag3", schedule
    out = []
    sent = 0
    for index, tid in enumerate(ids):
        full = tok.decode(ids[: index + 1])
        stop = max(sent, len(full) - 3)
        out.append((full[sent:stop], [tid]))
        sent = stop
    out.append((tok.decode(ids)[sent:], []))
    return out


# ── parser construction ────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {
                "type": "object",
                "properties": {key: {"type": kind} for key, kind in props},
            },
        },
    }
    for name, props in (
        ("calc", [("value", "integer")]),
        ("echo", [("text", "string"), ("note", "string")]),
    )
]


def _ensure_registered() -> None:
    """Register the v41 adapters when the local shim runs (no-op in-image)."""
    from vllm.parser.deepseek_v41 import DeepSeekV41Parser
    from vllm.parser.engine.adapters import make_adapters
    from vllm.reasoning import ReasoningParserManager
    from vllm.tool_parsers import ToolParserManager

    if ReasoningParserManager.get_reasoning_parser("deepseek_v41") is None:
        reasoning_adapter, tool_adapter = make_adapters(DeepSeekV41Parser)
        ReasoningParserManager._registry["deepseek_v41"] = reasoning_adapter
    if ToolParserManager.get_tool_parser("deepseek_v41") is None:
        _, tool_adapter = make_adapters(DeepSeekV41Parser)
        ToolParserManager._registry["deepseek_v41"] = tool_adapter


def make_request(tools, thinking: bool, tool_choice: Any = "auto"):
    from vllm.entrypoints.openai.chat_completion.protocol import ChatCompletionRequest

    kwargs = dict(
        model="deepseek-v41-dsml-test",
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        tool_choice=tool_choice,
        include_reasoning=True,
        chat_template_kwargs={"thinking": thinking},
    )
    try:
        return ChatCompletionRequest(**kwargs)
    except Exception:  # pydantic variant without one of the kwargs
        return ChatCompletionRequest.model_validate(kwargs)


def make_parser(tok: FakeTokenizer, tools, thinking: bool):
    from vllm.parser.parser_manager import ParserManager

    _ensure_registered()
    cls = ParserManager.get_parser(
        tool_parser_name="deepseek_v41",
        reasoning_parser_name="deepseek_v41",
        enable_auto_tools=True,
    )
    assert cls is not None, "deepseek_v41 parser not available"
    parser = cls(tok, tools, chat_template_kwargs={"thinking": thinking})
    prompt_ids = [THINK_START_ID if thinking else THINK_END_ID]
    return parser, prompt_ids


def stream(parser, request, prompt_ids, deltas):
    """Drive ``parse_delta``; return (reasoning, content, [(name, args_dict)])."""
    import json

    reasoning = ""
    content = ""
    calls: dict[int, list[str]] = {}
    for index, (text, ids) in enumerate(deltas):
        delta = parser.parse_delta(
            text,
            ids,
            request,
            prompt_token_ids=prompt_ids,
            finished=index == len(deltas) - 1,
        )
        if delta is None:
            continue
        reasoning += delta.reasoning or ""
        content += delta.content or ""
        for call in delta.tool_calls or []:
            merged = calls.setdefault(call.index, ["", ""])
            merged[0] += (call.function.name or "") if call.function else ""
            merged[1] += (call.function.arguments or "") if call.function else ""
    return (
        reasoning,
        content,
        [(name, json.loads(args or "{}")) for _, (name, args) in sorted(calls.items())],
    )


def parse_all(tok, ids, thinking, schedule, tools=TOOLS, tool_choice: Any = "auto"):
    """Parse *ids* under one schedule; return (reasoning, content, calls)."""
    import json

    parser, prompt_ids = make_parser(tok, tools, thinking)
    if not tools and tool_choice == "auto":
        tool_choice = None  # real vLLM rejects tool_choice without tools (as the API server would never send it)
    request = make_request(tools, thinking, tool_choice)
    if schedule != "nonstream":
        return stream(parser, request, prompt_ids, deltas_for(tok, ids, schedule))
    reasoning, content, calls = parser.parse(
        tok.decode(ids),
        request,
        enable_auto_tools=True,
        model_output_token_ids=list(ids),
    )
    return (
        reasoning or "",
        content or "",
        [(call.name, json.loads(call.arguments or "{}")) for call in calls or []],
    )