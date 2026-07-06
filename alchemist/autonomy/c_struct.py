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
        # comma-separated declarators share a type: `int a, b;`
        m = re.match(r"^(?P<type>.+?)(?P<decls>[\w\s,*\[\]]+)$", stmt)
        # simpler: strip array subscripts, then last token is the name
        cleaned = re.sub(r"\[[^\]]*\]", "", stmt)
        # split off the last declarator group by commas
        head, _, last = cleaned.rpartition(",")
        decl = (last or cleaned).strip()
        toks = decl.replace("*", " * ").split()
        if len(toks) < 2:
            continue
        name = toks[-1]
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            continue
        ctype = " ".join(t for t in toks[:-1] if t != "*").strip()
        if ctype:
            fields[name] = ctype
        # also register earlier comma-declarators with the same base type
        if head:
            base = " ".join(t for t in toks[:-1] if t != "*").strip()
            for extra in head.split(","):
                e = extra.replace("*", " ").split()
                if e and re.fullmatch(r"[A-Za-z_]\w*", e[-1]):
                    fields.setdefault(e[-1], base)
    return fields
