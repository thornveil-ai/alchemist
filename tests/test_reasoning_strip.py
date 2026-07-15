"""Reasoning-model output handling (Phase 3, Nemotron A/B): reasoning models emit the
chain of thought inside `content`, usually WITHOUT an opening <think> (the chat template
supplies it), so only a trailing </think> survives. The client must keep only the answer
after the last </think>, or every fill's JSON/code extraction breaks. Model-agnostic."""

from __future__ import annotations

from alchemist.llm.client import AlchemistLLM


def _c():
    return AlchemistLLM.__new__(AlchemistLLM)  # no network at construction


def test_nemotron_inline_reasoning_stripped():
    nemo = ('We map 0 to DELETE, let me write the match.\n\n</think>\n\n'
            '{"content": "fn http_method_str(m: i32) -> &static str { }"}')
    out = _c()._extract_json(nemo)
    assert out and out.get("content", "").startswith("fn http_method_str")


def test_clean_and_paired_and_multi_still_parse():
    c = _c()
    assert c._extract_json('{"content": "x"}') == {"content": "x"}
    assert c._extract_json('<think>hmm</think>{"content":"y"}') == {"content": "y"}
    assert c._extract_json('a</think>b</think>{"content":"z"}') == {"content": "z"}
