# SPDX-License-Identifier: Apache-2.0
"""CPU-only proof that DSML structure exists only where the real token does,
merged with the structural-closer rule.

Cases (a)..(h) map to the delivery checklist in REPORT.md:

  (a) the #876 sample - a call *spelled* inside a code fence, tools offered:
      no tool call, the whole text preserved.
  (b) the same sample with no tools offered: the whole text is content.
  (c) a genuine-token call is parsed, streaming and non-streaming.
  (d) a genuine call whose string argument contains spelled closers keeps the
      argument intact; (d2) a *genuine* closer inside a string argument is
      still literal text (our structural-closer rule).
  (e) reasoning that quotes spelled markup, followed by a real call: exactly
      one correct call, the quote stays in reasoning.
  (f) a genuine ``<calls>`` opener with no invoke line and a spelled
      parameter: documented, and the text is not silently dropped.
  (g) the upstream PR's own shapes (adapted).
  (h) the kill switch: with provenance off the old (buggy) parse returns, so
      the flip really is a rollback.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

import dsml_fixtures as F

SCHEDULES = F.SCHEDULES
FENCE = "\x60\x60\x60"


def _call_text(name: str, params: str) -> str:
    return (
        F.CALLS_OPEN
        + F.INVOKE_OPEN
        + name
        + '">'
        + params
        + F.INVOKE_CLOSE
        + F.CALLS_CLOSE
    )


def _param(name: str, string: bool, value: str) -> str:
    kind = "true" if string else "false"
    return f'{F.PARAM_OPEN} name="{name}" string="{kind}">{value}{F.PARAM_CLOSE}'


CALL_SAMPLE = _call_text("calc", _param("value", False, "42"))

# The #876 shape: the model writes the call markup as an example inside a
# fenced block, spelled with ordinary tokens.
FENCE_SAMPLE = (
    "Here is the exact shape a tool call takes:\n\n"
    + FENCE
    + "text\n"
    + CALL_SAMPLE
    + "\n"
    + FENCE
    + "\n"
    + "Set value to 42."
)


def _ids(tok, *chunks):
    """Build ids from ``(text, genuine)`` chunks."""
    out = []
    for text, genuine in chunks:
        out.extend(tok.genuine(text) if genuine else tok.spelled(text))
    return out


# ── (a) / (b) the #876 shape ───────────────────────────────────────────────


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_a_spelled_call_in_code_fence_is_text_with_tools(schedule):
    tok = F.FakeTokenizer()
    ids = tok.spelled(FENCE_SAMPLE)
    reasoning, content, calls = F.parse_all(tok, ids, False, schedule, tools=F.TOOLS)
    assert calls == []
    assert content == FENCE_SAMPLE
    assert reasoning == ""


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_b_spelled_call_in_code_fence_is_text_without_tools(schedule):
    tok = F.FakeTokenizer()
    ids = tok.spelled(FENCE_SAMPLE)
    reasoning, content, calls = F.parse_all(tok, ids, False, schedule, tools=None)
    assert calls == []
    assert content == FENCE_SAMPLE


def test_b_spelled_call_is_text_when_tool_choice_none():
    tok = F.FakeTokenizer()
    ids = tok.spelled("Sure. " + CALL_SAMPLE)
    _, content, calls = F.parse_all(tok, ids, False, "per_token", tool_choice="none")
    assert calls == []
    assert content == "Sure. " + CALL_SAMPLE


# ── (c) a genuine-token call ───────────────────────────────────────────────


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_c_genuine_call_is_parsed(schedule):
    tok = F.FakeTokenizer()
    ids = tok.genuine(CALL_SAMPLE)
    reasoning, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("calc", {"value": 42})]
    assert content.strip() == ""
    assert reasoning == ""


def test_c_genuine_call_with_two_parameters():
    tok = F.FakeTokenizer()
    text = _call_text(
        "echo",
        _param("text", True, "hello") + _param("note", True, "world"),
    )
    _, _, calls = F.parse_all(tok, tok.genuine(text), False, "per_token")
    assert calls == [("echo", {"text": "hello", "note": "world"})]


# ── (d) closers inside a string argument ───────────────────────────────────

SPELLED_INNER = (
    "a"
    + F.PARAM_CLOSE
    + "b"
    + F.INVOKE_CLOSE
    + "c"
    + F.CALLS_CLOSE
    + "d"
)


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_d_spelled_closers_inside_string_argument_stay_text(schedule):
    tok = F.FakeTokenizer()
    ids = _ids(
        tok,
        (
            F.CALLS_OPEN + F.INVOKE_OPEN + 'echo">' + F.PARAM_OPEN
            + ' name="text" string="true">',
            True,
        ),
        (SPELLED_INNER, False),
        (F.INVOKE_CLOSE + F.CALLS_CLOSE, True),
    )
    _, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("echo", {"text": SPELLED_INNER})]
    assert content.strip() == ""


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_d2_genuine_closer_inside_string_argument_is_literal(schedule):
    """Our own rule, on genuine tokens: a real closer inside a value is text
    unless structure (a new parameter head, or the end of the arguments)
    follows it."""
    tok = F.FakeTokenizer()
    inner = "a" + F.PARAM_CLOSE + "b"
    ids = _ids(
        tok,
        (
            F.CALLS_OPEN + F.INVOKE_OPEN + 'echo">' + F.PARAM_OPEN
            + ' name="text" string="true">a',
            True,
        ),
        ("", False),
        (F.PARAM_CLOSE, True),
        ("b", False),
        (F.PARAM_CLOSE + F.INVOKE_CLOSE + F.CALLS_CLOSE, True),
    )
    _, _, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("echo", {"text": inner})]


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_d3_genuine_closer_followed_by_next_head_is_structure(schedule):
    """The structural rule must not eat real structure: a closer followed by a
    new parameter head ends the value."""
    tok = F.FakeTokenizer()
    text = _call_text(
        "echo",
        _param("text", True, "a") + _param("note", True, "b"),
    )
    _, _, calls = F.parse_all(tok, tok.genuine(text), False, schedule)
    assert calls == [("echo", {"text": "a", "note": "b"})]


# ── (e) reasoning quoting the format, then a real call ─────────────────────

QUOTE = "I could write " + CALL_SAMPLE + " but the real call follows."


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_e_quoted_markup_in_reasoning_then_real_call(schedule):
    tok = F.FakeTokenizer()
    ids = _ids(tok, ("Plan. ", False), (QUOTE, False), (CALL_SAMPLE, True))
    reasoning, content, calls = F.parse_all(tok, ids, True, schedule)
    assert calls == [("calc", {"value": 42})]
    assert reasoning == "Plan. " + QUOTE
    assert content.strip() == ""


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_e2_quoted_markup_in_reasoning_alone_is_not_a_call(schedule):
    tok = F.FakeTokenizer()
    ids = _ids(tok, ("Plan. ", False), (QUOTE, False))
    reasoning, content, calls = F.parse_all(tok, ids, True, schedule)
    assert calls == []
    assert reasoning == "Plan. " + QUOTE


# ── (f) genuine opener, no invoke line, spelled parameter ──────────────────

F_REMAINDER = (
    " the params are: " + F.PARAM_OPEN + ' name="x" string="true">v' + F.PARAM_CLOSE
)


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_f_calls_opener_without_invoke_keeps_text(schedule):
    """Documented behaviour: no call is produced and the body is surfaced as
    content (stock dropped it silently: TOOL_PREAMBLE has no content event)."""
    tok = F.FakeTokenizer()
    ids = _ids(tok, (F.CALLS_OPEN, True), (F_REMAINDER, False))
    reasoning, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == []
    assert content.strip() == F_REMAINDER.strip()
    assert reasoning == ""


# ── (g) the upstream PR's own shapes, adapted ──────────────────────────────


@pytest.mark.parametrize("schedule", ["nonstream", "per_token"])
def test_g1_text_call_is_content(schedule):
    tok = F.FakeTokenizer()
    ids = tok.spelled("Before " + CALL_SAMPLE + " after")
    _, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == []
    assert content == "Before " + CALL_SAMPLE + " after"


@pytest.mark.parametrize("schedule", ["nonstream", "per_token"])
def test_g2_text_call_stays_reasoning(schedule):
    tok = F.FakeTokenizer()
    ids = tok.spelled("Before " + CALL_SAMPLE + " after")
    reasoning, content, calls = F.parse_all(tok, ids, True, schedule)
    assert calls == []
    assert reasoning == "Before " + CALL_SAMPLE + " after"
    assert content.strip() == ""


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_g3_genuine_atom_without_marker_is_text(schedule):
    tok = F.FakeTokenizer()
    ids = _ids(tok, ("<", False), (F.ATOM, True), (" inv", False))
    _, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == []
    assert content == "<" + F.ATOM + " inv"


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_g4_text_twins_around_call(schedule):
    tok = F.FakeTokenizer()
    twin = CALL_SAMPLE.replace(">42<", ">99<")
    ids = _ids(
        tok,
        ("before ", False),
        (CALL_SAMPLE, True),
        (" após " + twin + " end", False),
    )
    _, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("calc", {"value": 42})]
    assert content.strip().startswith("before")
    assert "99" in content


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_g5_text_call_between_calls(schedule):
    tok = F.FakeTokenizer()
    invoke_only = CALL_SAMPLE.removeprefix(F.CALLS_OPEN).removesuffix(F.CALLS_CLOSE)
    middle = "text " + invoke_only + " 🙂 "
    ids = _ids(
        tok,
        (F.CALLS_OPEN, True),
        (invoke_only, True),
        (middle, False),
        (invoke_only + F.CALLS_CLOSE, True),
    )
    _, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("calc", {"value": 42}), ("calc", {"value": 42})]
    assert "text " in content and "🙂" in content


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_g6_emoji_then_twin(schedule):
    tok = F.FakeTokenizer()
    twin = CALL_SAMPLE.replace(">42<", ">99<")
    ids = _ids(tok, ("🙂", False), (CALL_SAMPLE, True), (twin, False))
    _, content, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("calc", {"value": 42})]
    assert content.strip() == "🙂" + twin


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_g7_delayed_bos_before_call(schedule):
    tok = F.FakeTokenizer()
    ids = [F.BOS_ID] + tok.genuine(CALL_SAMPLE)
    _, _, calls = F.parse_all(tok, ids, False, schedule)
    assert calls == [("calc", {"value": 42})]


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_g8_partial_marker_flushes_as_text(schedule):
    tok = F.FakeTokenizer()
    text = "До " + F.INVOKE_OPEN + "calc"
    ids = _ids(tok, ("До ", False), (text.removeprefix("До "), True))
    reasoning, content, calls = F.parse_all(tok, ids, True, schedule)
    assert calls == []
    assert reasoning.strip() == text.strip()


# ── (h) kill switch ────────────────────────────────────────────────────────


def test_h_provenance_off_restores_old_parse():
    """VLLM_DSV41_DSML_TOKEN_PROVENANCE=0 must give back the previous (buggy)
    parse, so an operator rollback is a real env flip."""
    code = textwrap.dedent(
        """
        import json, os, sys
        for _p in (os.environ.get("VLLM_SHIM_PATH"), os.environ["PORT_TESTS_DIR"]):
            if _p:
                sys.path.insert(0, _p)
        import dsml_fixtures as F
        import test_dsml_token_provenance as T
        tok = F.FakeTokenizer()
        reasoning, content, calls = F.parse_all(
            tok, tok.spelled(T.FENCE_SAMPLE), False, "one_chunk", tools=F.TOOLS
        )
        print(json.dumps({"calls": calls, "content": content}))
        """
    )
    env = {
        **os.environ,
        "VLLM_DSV41_DSML_TOKEN_PROVENANCE": "0",
        "PORT_TESTS_DIR": os.path.dirname(os.path.abspath(__file__)),
    }
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["calls"] == [["calc", {"value": 42}]]
