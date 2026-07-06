"""Parse C struct field -> type maps from a header, for ANY library.

The shim generator needs the field types of a state struct to emit type-correct
accessors. Hardcoding them (as the zlib bring-up did) doesn't generalize. This
derives `{field: c_type}` for an arbitrary struct in an arbitrary header, so the
oracle-shim synthesis is library-agnostic — a core piece of onboarding a new
library (docs/PATH_TO_AUTONOMY.md, WS1/WS5).

Handles the common shapes:
  * `struct NAME { ... };`
  * `typedef struct [tag] { ... } [FAR] NAME;`   (name is the typedef alias)
fields with pointers, arrays, and multi-word types (`unsigned long`,
`struct ct_data_s`). Nested inline unions/structs are skipped (rare in state
structs; they'd need a fuller parser).
"""

from __future__ import annotations

import re

try:
    from alchemist.implementer.reference_probe import _blank_comments_strings
except Exception:  # pragma: no cover - fallback if import graph shifts
    def _blank_comments_strings(t: str) -> str:
        return t


def _brace_match_back(text: str, close_idx: int) -> int | None:
    depth = 0
    i = close_idx
    while i >= 0:
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0:
                return i
        i -= 1
    return None


def _brace_match_fwd(text: str, open_idx: int) -> int | None:
    depth = 0
    for j in range(open_idx, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    return None


def _find_struct_body(source: str, struct_name: str) -> str | None:
    # Parse the comment/string-blanked copy so field TYPES don't absorb the
    # trailing/leading comment text of neighbouring fields (positions preserved).
    clean = _blank_comments_strings(source)
    esc = re.escape(struct_name)
    # typedef ... } [FAR] NAME ;
    for m in re.finditer(r"\}\s*(?:FAR\s+|_far\s+)?" + esc + r"\s*;", clean):
        open_i = _brace_match_back(clean, m.start())
        if open_i is not None:
            return clean[open_i + 1 : m.start()]
    # struct NAME { ... }
    m = re.search(r"\bstruct\s+" + esc + r"\s*\{", clean)
    if m:
        open_i = clean.index("{", m.start())
        close = _brace_match_fwd(clean, open_i)
        if close is not None:
            return clean[open_i + 1 : close]
    return None


_DEFINE_RE = re.compile(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+(.+?)[ \t]*(?:/\*.*|//.*)?$",
                        re.MULTILINE)
_ARITH_OK = re.compile(r"^[\d\s+\-*/()<>|&^~]+$")


def resolve_c_defines(source: str) -> dict[str, int]:
    """Resolve `#define NAME <int-expr>` macros to integer VALUES, following
    references between them (e.g. `HEAP_SIZE (2*L_CODES+1)` -> 573). Only pure
    integer-arithmetic macros are resolved; function-like and string macros are
    skipped. Lets the translator INLINE C constant values, which don't exist as
    Rust consts — the #1 compile failure on ported functions (MAX_BITS, HEAP_SIZE,
    L_CODES...)."""
    raw: dict[str, str] = {}
    for m in _DEFINE_RE.finditer(source):
        name, val = m.group(1), m.group(2).strip()
        if "(" in name or not val:  # skip function-like macros
            continue
        raw[name] = val
    resolved: dict[str, int] = {}

    def resolve(name: str, seen: frozenset = frozenset()) -> int | None:
        if name in resolved:
            return resolved[name]
        if name not in raw or name in seen:
            return None
        expr = raw[name].replace("U", "").replace("L", "")

        def sub(mm):
            n = mm.group(0)
            if n in resolved:
                return str(resolved[n])
            r = resolve(n, seen | {name})
            return str(r) if r is not None else "None"
        e = re.sub(r"[A-Za-z_]\w*", sub, expr)
        if "None" in e or not _ARITH_OK.match(e):
            return None
        try:
            v = eval(e, {"__builtins__": {}}, {})  # sandboxed: arithmetic only
        except Exception:
            return None
        if isinstance(v, int):
            resolved[name] = v
            return v
        return None

    for n in list(raw):
        resolve(n)
    return resolved


def parse_struct_fields(source: str, struct_name: str) -> dict[str, str]:
    """Return {field_name: c_type} for `struct_name` found in `source`.

    Empty dict if the struct isn't found. Pointer `*` and array `[...]` are
    stripped from the type; the returned type is the declared base type tokens
    (e.g. `unsigned long`, `uInt`, `struct ct_data_s`).
    """
    body = _find_struct_body(source, struct_name)
    if body is None:
        return {}
    # drop any nested brace groups (inline union/struct) so ';' splitting is safe
    body = re.sub(r"\{[^{}]*\}", " ", body)
    fields: dict[str, str] = {}
    for stmt in body.split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith("#") or stmt.startswith("//"):
            continue
        cleaned = re.sub(r"\[[^\]]*\]", "", stmt)  # drop array subscripts
        # `TYPE [*]name0, [*]name1, ...` — the type comes from the first declarator,
        # and every comma-declarator shares that base type.
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        first = parts[0].replace("*", " * ").split()
        if len(first) < 2:
            continue
        name0 = first[-1]
        base = " ".join(t for t in first[:-1] if t != "*").strip()
        if not base or not re.fullmatch(r"[A-Za-z_]\w*", name0):
            continue
        fields[name0] = base
        for extra in parts[1:]:
            toks = extra.replace("*", " ").split()
            if toks and re.fullmatch(r"[A-Za-z_]\w*", toks[-1]):
                fields.setdefault(toks[-1], base)
    return fields
