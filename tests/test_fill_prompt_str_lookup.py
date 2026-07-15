"""Scaffolding fix (P1.5): the fill prompt must SHOW the model the known str_lookup /
rust_body answer table (the exact strings the differential vectors already contain),
not summarize it away. Withholding it forced the model to reproduce a library's string
table from memory against a hidden oracle — impossible for any model (http_method_str)."""

from __future__ import annotations

from alchemist.implementer.tdd_generator import TDDGenerator
from alchemist.extractor.schemas import AlgorithmSpec, Parameter, TestVector


def _str_lookup_alg():
    return AlgorithmSpec(
        name="http_method_str", display_name="http_method_str", category="utility",
        description="Map an HTTP method enum to its string.",
        inputs=[Parameter(name="m", rust_type="i32", c_type="enum http_method",
                          description="method")],
        return_type="&'static str",
        test_vectors=[
            TestVector(description="lookup_0", source="C ref", inputs={},
                       expected_output='assert_eq!(super::http_method_str(0), "DELETE");',
                       tolerance="rust_body"),
            TestVector(description="lookup_1", source="C ref", inputs={},
                       expected_output='assert_eq!(super::http_method_str(1), "GET");',
                       tolerance="rust_body"),
            TestVector(description="lookup_2", source="C ref", inputs={},
                       expected_output='assert_eq!(super::http_method_str(2), "POST");',
                       tolerance="rust_body"),
        ],
    )


class _FakeResp:
    content = "unimplemented!()"
    error = ""


def test_str_lookup_table_is_shown_in_fill_prompt():
    gen = TDDGenerator()
    gen._cached_ctx = None
    captured = {}

    def fake_call_structured(messages, **kw):
        captured["prompt"] = messages[0]["content"]
        return _FakeResp()

    gen.llm.call_structured = fake_call_structured
    try:
        gen._prompt_for_impl(_str_lookup_alg(), current_body="unimplemented!()",
                             module_source="")
    except Exception:  # noqa: BLE001 — we only need the captured prompt, not the response
        pass
    prompt = captured.get("prompt", "")
    assert prompt, "prompt was never built/sent"
    # The exact answer strings must appear verbatim so the model copies, not guesses.
    for lit in ('"DELETE"', '"GET"', '"POST"'):
        assert lit in prompt, f"{lit} missing from fill prompt — model would have to guess"
    assert "assert_eq!(super::http_method_str(0)" in prompt
