"""Inline trivial `static inline` C helpers at their call sites.

A `static inline` header helper (e.g. libfixmath's `fix_abs`, `fix16_from_int`,
`fix16_add`) is compiler-inlined anyway and is too small to independently
differentially-verify. Left as its own translatable function it (a) refuses
("no test vectors") and (b) if it lands in a different crate than its caller,
the caller can't resolve it — which sank the first libfixmath run. Inlining the
single-`return`-expression helpers at their call sites makes every real function
self-contained, exactly as `fix16_sqrt` needed by hand.

Scope (conservative on purpose): only helpers whose body is a single
`return <expr>;`. Multi-statement inlines are left alone. Applied to fixpoint so
a helper that calls another helper resolves. Behaviour-preserving: it reproduces
what the C compiler does with `static inline`.
"""
from __future__ import annotations

import re

# static [inline] TYPE NAME(params) { return EXPR; }  — TYPE may have * and words
_HELPER_RE = re.compile(
    r"static\s+inline\s+[\w\s\*]+?\b(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*"
    r"\{\s*return\b(?P<expr>.*?);\s*\}",
    re.S,
)
_IDENT = re.compile(r"[A-Za-z_]\w*")


def _param_names(params: str) -> list[str]:
    params = params.strip()
    if not params or params == "void":
        return []
    names = []
    for p in params.split(","):
        toks = _IDENT.findall(p)
        if toks:
            names.append(toks[-1])  # the identifier after the type is the name
    return names


def _split_top_level_args(s: str) -> list[str]:
    """Split call-argument text on top-level commas (respecting nested parens)."""
    args, depth, cur = [], 0, []
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        args.append("".join(cur).strip())
    return args


def _match_call_args(text: str, open_paren: int) -> tuple[str, int] | None:
    """Given index of '(' return (inner_text, index_after_closing_paren)."""
    depth = 0
    for i in range(open_paren, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1 : i], i + 1
    return None


def _substitute(expr: str, params: list[str], args: list[str]) -> str:
    """Replace each param identifier in expr with (arg), preserving precedence."""
    if len(params) != len(args):
        return expr  # arity mismatch — refuse to inline (safety)
    mapping = {p: f"({a})" for p, a in zip(params, args)}

    def repl(m):
        tok = m.group(0)
        return mapping.get(tok, tok)

    return "(" + _IDENT.sub(repl, expr.strip()) + ")"


def _inline_once(src: str, helpers: dict[str, tuple[list[str], str]]) -> tuple[str, bool]:
    changed = False
    for name, (params, expr) in helpers.items():
        out = []
        i = 0
        pat = re.compile(r"\b" + re.escape(name) + r"\s*\(")
        while True:
            m = pat.search(src, i)
            if not m:
                out.append(src[i:])
                break
            open_paren = m.end() - 1
            got = _match_call_args(src, open_paren)
            if got is None:
                out.append(src[i : m.end()])
                i = m.end()
                continue
            inner, after = got
            args = _split_top_level_args(inner)
            out.append(src[i : m.start()])
            out.append(_substitute(expr, params, args))
            i = after
            changed = True
        src = "".join(out)
    return src, changed


def inline_trivial_static_inlines(src: str) -> tuple[str, list[str]]:
    """Return (transformed_source, inlined_helper_names).

    Collects single-return `static inline` helpers, inlines their call sites to
    fixpoint, and deletes their definitions. Idempotent and safe: unknown/complex
    inlines are left untouched.
    """
    helpers: dict[str, tuple[list[str], str]] = {}
    for m in _HELPER_RE.finditer(src):
        helpers[m.group("name")] = (_param_names(m.group("params")), m.group("expr"))
    if not helpers:
        return src, []

    # Remove the helper DEFINITIONS first (so their own `return name(...)` bodies
    # don't get self-inlined) — collect spans, delete in reverse.
    spans = [(m.start(), m.end()) for m in _HELPER_RE.finditer(src)]
    for a, b in sorted(spans, reverse=True):
        src = src[:a] + src[b:]

    # Inline call sites to fixpoint (helper-calls-helper).
    for _ in range(8):
        src, changed = _inline_once(src, helpers)
        if not changed:
            break
    return src, sorted(helpers)
