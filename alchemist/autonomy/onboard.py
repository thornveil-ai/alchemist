"""Auto-onboarding for a C source file — the pieces that turn a hand-written
`setup_*.py` into `alchemist translate ./lib`.

Specced by real failures translating ArduPilot's `crc.cpp`:
  1. Real C spreads data across MANY `static const` tables (crc.cpp had 7, not
     the 3 first hardcoded) — miss one and the fill can't compile.
  2. Functions call each other, so bodies must be filled in call-graph
     (dependency) order — `crc_xmodem` calls `crc_xmodem_update`; fill the
     helper first.

This module discovers, from source alone: every lookup table (with a Rust type),
every function definition (name / return / params / callees), and a dependency
fill order. Library-agnostic; the clean-blanked copy is parsed so comment text
(e.g. base64's ASCII-order comments full of numbers) never pollutes results.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    from alchemist.implementer.reference_probe import _blank_comments_strings
except Exception:  # pragma: no cover - fallback if import graph shifts
    def _blank_comments_strings(t: str) -> str:
        return t

# C scalar type -> Rust scalar type. Longest match on the trailing token wins.
_CTY2RTY = {
    "uint8_t": "u8", "uint16_t": "u16", "uint32_t": "u32", "uint64_t": "u64",
    "int8_t": "i8", "int16_t": "i16", "int32_t": "i32", "int64_t": "i64",
    "uchar": "u8", "uint": "u32", "ushort": "u16", "ulong": "u64",
    "char": "u8", "short": "i16", "int": "i32", "long": "i64",
    "float": "f32", "double": "f64", "size_t": "usize", "bool": "bool",
}

_CONTROL_KW = {"if", "for", "while", "switch", "return", "sizeof", "do", "else"}


def c_to_rust_scalar(c_type: str) -> str:
    """Map a C scalar type string to a Rust scalar type (best effort)."""
    joined = " ".join(c_type.replace("const", "").split())
    # `unsigned X` compounds first — else the trailing token maps `int`->i32.
    for k, v in (("unsigned char", "u8"), ("unsigned short", "u16"),
                 ("unsigned long long", "u64"), ("unsigned int", "u32"),
                 ("unsigned long", "u64"), ("unsigned", "u32")):
        if k in joined:
            return v
    toks = joined.split()
    if toks and toks[-1] in _CTY2RTY:
        return _CTY2RTY[toks[-1]]
    return "u32"


def _match_brace(text: str, open_idx: int) -> int | None:
    depth = 0
    for j in range(open_idx, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    return None


@dataclass
class CTable:
    name: str
    rust_type: str
    values: list[int]

    def rust_const(self) -> str:
        """Emit `pub const NAME: [ty; N] = [...];` (uppercased name)."""
        return "pub const %s: [%s; %d] = [%s];" % (
            self.name.upper(), self.rust_type, len(self.values),
            ", ".join(str(v) for v in self.values))


_ESC = {"\\n": 10, "\\t": 9, "\\r": 13, "\\0": 0, "\\\\": 92, "\\'": 39, '\\"': 34}


def _parse_table_values(body: str) -> list[int]:
    """Numbers (dec/hex) AND char literals ('A', '\\n') — real C tables use both
    (base64's encode table is char literals, its decode table is numbers)."""
    vals: list[int] = []
    for tok in re.finditer(r"0x[0-9a-fA-F]+|'(?:\\.|[^'])'|\d+", body):
        t = tok.group(0)
        if t.startswith("'"):
            inner = t[1:-1]
            vals.append(_ESC.get(inner, ord(inner[-1])))
        else:
            vals.append(int(t, 0))
    return vals


def extract_tables(source: str) -> dict[str, CTable]:
    """Every `static const T name[...] = { ... }` in the source, typed.

    Parses the comment/string-blanked copy so numbers inside comments (e.g.
    base64's `/* '0','1',.. */` rows) never leak into the values. Handles both
    numeric and char-literal element lists.
    """
    out: dict[str, CTable] = {}
    for m in re.finditer(
        r"static\s+const\s+([\w ]+?)\s+(\w+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\}\s*;",
        source, re.S,
    ):
        cty, name, body = m.group(1).strip(), m.group(2), m.group(3)
        # strip comments from the body (keep char literals), then parse values
        body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
        body = re.sub(r"//[^\n]*", " ", body)
        vals = _parse_table_values(body)
        if vals:
            out[name] = CTable(name, c_to_rust_scalar(cty), vals)
    return out


def gen_fuzz_lengths(n: int, max_len: int = 4096) -> list[int]:
    """`n` diverse input lengths for deep differential fuzzing: every boundary
    value (powers of two, block edges) first, then a deterministic spread up to
    `max_len`. Deterministic (no RNG) so runs are reproducible."""
    boundary = [0, 1, 2, 3, 4, 5, 7, 8, 15, 16, 17, 31, 32, 33, 55, 56, 57, 63, 64,
                65, 71, 127, 128, 129, 191, 192, 255, 256, 257, 383, 384, 511, 512,
                513, 1023, 1024, 1025, 2047, 2048, 4095, 4096]
    out = list(dict.fromkeys(x for x in boundary if x <= max_len))
    x = 12345
    while len(out) < n:
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        v = x % (max_len + 1)
        if v not in out:
            out.append(v)
    return out[:n]


def extract_char_defines(source: str) -> dict[str, int]:
    """`#define NAME 'x'` byte constants (e.g. base64's `BASE64_PAD '='`). The
    code compares bytes against these; emit them as `pub const NAME: u8`."""
    out: dict[str, int] = {}
    for m in re.finditer(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+'(\\?.)'", source, re.M):
        name, ch = m.group(1), m.group(2)
        out[name] = _ESC.get("\\" + ch[-1], ord(ch[-1])) if ch.startswith("\\") else ord(ch)
    return out


@dataclass
class CFunc:
    name: str
    ret: str
    params: str
    body: str = ""
    calls: set[str] = field(default_factory=set)


def discover_functions(source: str) -> dict[str, CFunc]:
    """Every top-level function DEFINITION, with its callees (restricted to
    other functions defined in the same source)."""
    clean = _blank_comments_strings(source)
    funcs: dict[str, CFunc] = {}
    # TYPE [*] NAME ( params ) [const] {   — allow leading static/inline, multiline params
    for m in re.finditer(
        r"(?:^|\n)[ \t]*"
        r"((?:static|inline|extern)\s+)*"          # storage
        r"([A-Za-z_][\w \t]*?[\w])"                # return type tokens (one line)
        r"[ \t\n\*]+([A-Za-z_]\w*)[ \t\n]*"        # newline/space/star then NAME (K&R)
        r"\(([^;{]*?)\)[ \t\n]*(?:const[ \t]*)?\{",  # ( params ) {
        clean,
    ):
        name = m.group(3)
        if name in _CONTROL_KW:
            continue
        ret = ((m.group(1) or "") + m.group(2)).strip()
        params = " ".join(m.group(4).split())
        open_brace = clean.index("{", m.end() - 1)
        close = _match_brace(clean, open_brace)
        body = clean[open_brace + 1: close] if close is not None else ""
        funcs[name] = CFunc(name=name, ret=ret, params=params, body=body)
    names = set(funcs)
    for f in funcs.values():
        for cm in re.finditer(r"\b(\w+)\s*\(", f.body):
            callee = cm.group(1)
            if callee in names and callee != f.name:
                f.calls.add(callee)
    return funcs


def fill_order(funcs: dict[str, CFunc]) -> list[str]:
    """Dependency-first order: a function appears AFTER every function it calls,
    so helpers are filled before their callers. Cycle-tolerant (breaks cycles at
    the back-edge, preserving a stable order)."""
    state: dict[str, int] = {}  # 0 = visiting, 1 = done
    order: list[str] = []

    def visit(n: str) -> None:
        if state.get(n) == 1 or state.get(n) == 0:
            return
        state[n] = 0
        for dep in sorted(funcs[n].calls):
            if dep in funcs:
                visit(dep)
        state[n] = 1
        order.append(n)

    for n in funcs:  # insertion order (source order) is the stable tiebreak
        visit(n)
    return order
