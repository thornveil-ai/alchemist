"""Mechanical pre-translation — do the deterministic parts by rule, not by model.

A lot of what the model gets wrong isn't the algorithm — it's the scaffolding: the
canonical counting loop, the `as usize` on an index, the shift/mask operators. Those
are a mechanical rewrite, not a reasoning task. Doing them deterministically and
handing the model a partial Rust skeleton means there is LESS for it to get wrong, so
the first shot succeeds more often — at the SAME latency (the model generates less).

This is a hint, not the answer: the model still fills the semantic core, and the
oracle still gates the result byte-exact.
"""

from __future__ import annotations

import re


def mechanical_pretranslate(c_body: str) -> str:
    """Rewrite the mechanical C scaffolding of a body into Rust. Deterministic, no
    model. The canonical `for (T i=0; i<N; i++)` becomes `for i in 0..(N as usize)`,
    and array indices are cast to usize -- the two things the model most often fumbles."""
    r = c_body
    # canonical counting loop -> Rust range loop (handles ++i and i++)
    r = re.sub(
        r"for\s*\(\s*(?:[A-Za-z_][\w ]*\s+)?([A-Za-z_]\w*)\s*=\s*0\s*;\s*"
        r"\1\s*<\s*([A-Za-z_]\w*)\s*;\s*(?:\+\+\1|\1\+\+)\s*\)",
        r"for \1 in 0..(\2 as usize)", r)
    # array indexing with a bare identifier -> cast to usize (Rust requires it)
    r = re.sub(r"\[\s*([A-Za-z_]\w*)\s*\]", r"[\1 as usize]", r)
    return r


def pretranslate_hint(c_body: str) -> str:
    """A fill-prompt hint block: the mechanically pre-translated skeleton the model
    should complete (only if the rewrite actually changed something)."""
    skeleton = mechanical_pretranslate(c_body)
    if skeleton.strip() == c_body.strip():
        return ""
    return ("## Mechanical skeleton (loops + index casts already done in Rust; keep "
            "these, fill the rest)\n```rust\n%s\n```" % skeleton)
