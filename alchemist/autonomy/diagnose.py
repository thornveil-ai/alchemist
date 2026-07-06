"""Automated diagnosis (Tier 1 #3) — the agent that replaces the human when a
function is hard.

The single deepest hand-jam in the whole pipeline was ME: when a fill plateaus, a
human reads the model's Rust against the C, names the coherent-model mismatch (the
loop-cursor bug, the pointer->index bug, the output-index bug), fixes it, and
writes the idiom. This makes that a loop the model runs on itself: given the C,
the wrong Rust, and the exact differential failure, produce a STRUCTURED diagnosis
{root_cause, general_rule, fixed_function}, apply it, test, and iterate. The
`general_rule` is a reusable idiom the catalog can absorb — so the tool gets
smarter every time it's stuck, without a human in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    from alchemist.autonomy.live_repair import _strip_fences
except Exception:  # pragma: no cover
    def _strip_fences(s: str) -> str:
        return s.strip()

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string",
                       "description": "the specific C idiom that was mistranslated and why it diverges"},
        "general_rule": {"type": "string",
                         "description": "one reusable sentence: how this C idiom must map to safe Rust"},
        "fixed_function": {"type": "string",
                           "description": "the complete corrected `pub fn ...`"},
    },
    "required": ["root_cause", "general_rule", "fixed_function"],
}


@dataclass
class Diagnosis:
    fixed: bool
    root_cause: str
    general_rule: str
    rounds: int


def _diag_prompt(c_body: str, rust: str, failure: str) -> str:
    return (
        "A Rust function was translated from C but its behavior DIVERGES from the "
        "reference. Diagnose the ROOT CAUSE as a coherent-model mismatch — how a "
        "specific C idiom must map to safe Rust — then give a GENERAL RULE reusable "
        "on other functions, then the corrected function.\n\n"
        "Consider idioms that commonly mistranslate: pointer->index, buffer+length, "
        "loop-cursor increment placement, a manually-advanced output index vs the "
        "buffer, borrow-checker splits, fixed-array vs Vec sizing, C macro constants, "
        "signed/unsigned width and masking.\n\n"
        "## C reference (authoritative)\n```c\n%s\n```\n\n"
        "## Current Rust (diverges)\n```rust\n%s\n```\n\n"
        "## Differential failure (compile error / panic / expected-vs-got)\n%s\n\n"
        "Return root_cause, general_rule (ONE reusable sentence), and fixed_function "
        "(the COMPLETE corrected `pub fn`, body included)."
        % (c_body, rust, failure.strip()[:2000])
    )


def diagnose_and_fix(
    c_body: str,
    current_rust: str,
    failure_text: str,
    llm,
    apply_fixed: Callable[[str], None],
    run_test: Callable[[], tuple[bool, str]],
    max_rounds: int = 3,
    temperature: float = 0.0,
) -> Diagnosis:
    """Loop: diagnose -> apply fix -> test -> (on failure) re-diagnose with the new
    error. `apply_fixed(code)` splices the corrected function; `run_test()` returns
    (passed, failure_text). Refuses to claim success unless run_test passes."""
    root_cause = general_rule = ""
    for r in range(max_rounds):
        prompt = _diag_prompt(c_body, current_rust, failure_text)
        resp = llm.call_structured(
            messages=[{"role": "user", "content": prompt}],
            tool_name="diagnose",
            tool_schema=DIAGNOSIS_SCHEMA,
            max_tokens=2800,
            temperature=temperature,
        )
        d = getattr(resp, "structured", None) or {}
        root_cause = d.get("root_cause", "") or root_cause
        general_rule = d.get("general_rule", "") or general_rule
        fixed = _strip_fences(d.get("fixed_function", ""))
        if not fixed:
            break
        apply_fixed(fixed)
        passed, failure_text = run_test()
        current_rust = fixed
        if passed:
            return Diagnosis(True, root_cause, general_rule, r + 1)
    return Diagnosis(False, root_cause, general_rule, max_rounds)
