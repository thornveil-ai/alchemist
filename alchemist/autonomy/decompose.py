"""Decomposition — attack the fill ceiling by translating SMALL verified units.

The functions the model can't fill in one shot (AES rounds, Blowfish's key schedule)
are monoliths built from a few repeated sub-computations, usually hidden in mutating
statement macros like Blowfish's

    #define F(x,t) t = s[0][(x)>>24]; t += s[1][...]; t ^= s[2][...]; t += s[3][x&0xff];

Inlined, that macro turns one function into an unfillable wall. Extracted into a
standalone function `F(ctx, x) -> t`, it becomes a SMALL unit the model can translate
and the oracle can verify on its own — and the caller then calls the verified helper.
Decompose -> translate+verify each piece -> recompose. This is the lever that greens
the hard crypto without a stronger base model.
"""

from __future__ import annotations

import re


def extract_statement_macro(name: str, params_str: str, body: str, elem: str = "u32") -> dict:
    """Turn a mutating statement macro into a standalone-function spec.

    Infers the OUTPUT param (the one assigned in the body), the INPUT params, and the
    ctx/state objects it reaches through (`k->...`). Returns {rust_sig, output, inputs,
    ctx, is_verifiable} — a unit the pipeline can fill + differentially verify alone.
    """
    params = [p.strip() for p in params_str.split(",") if p.strip()]
    output = next((p for p in params
                   if re.search(r"\b" + re.escape(p) + r"\s*(?:[+\-*/^|&]|<<|>>)?=", body)),
                  params[-1] if params else "t")
    inputs = [p for p in params if p != output]
    ctx = sorted(set(re.findall(r"\b(\w+)\s*->", body)) - set(params))
    ctx = [c for c in ctx if c != output]
    args = ["%s: &Ctx" % c for c in ctx] + ["%s: %s" % (i, elem) for i in inputs]
    return {
        "rust_sig": "pub fn %s(%s) -> %s" % (name, ", ".join(args), elem),
        "output": output,
        "inputs": inputs,
        "ctx": ctx,
        # verifiable alone iff it has an input and produces one output (a pure sub-fn)
        "is_verifiable": bool(inputs) and bool(output),
    }


def decomposition_plan(fn, funcs: dict, macros: dict) -> list[str]:
    """Bottom-up sub-unit order for a hard function: the statement macros it expands
    plus the helper functions it calls, leaves first, then the function itself. Each
    unit is translated + verified independently before the caller is filled."""
    body = getattr(fn, "body", "")
    used_macros = [m for m in macros if re.search(r"\b" + re.escape(m) + r"\s*\(", body)]
    called = [c for c in re.findall(r"\b(\w+)\s*\(", body) if c in funcs and c != fn.name]
    # macros and callees first (the pieces), then the function that composes them
    return list(dict.fromkeys(used_macros + called + [fn.name]))
