"""Pillar 1 — the effect-footprint oracle.

The pure-function oracle verifies `input -> output bytes`. That's why crypto/codecs
work and anything touching global state is out of scope. This generalizes the
differential to the FULL OBSERVABLE FOOTPRINT of a call sequence:

    footprint = [captured return values] ++ [final bytes of every global/static]

C keeps its state in implicit file-scope globals; the coherent Rust model makes
that state EXPLICIT (a `GlobalState` struct threaded as `&mut`). Both run the same
driver over the same input and dump the same footprint; byte-exact-or-refused now
holds for effectful code, not just pure functions.

This is the moat: an oracle that verifies effectful C is what lets "verified-or-
refused" scale past the deterministic slice toward arbitrary C — model-agnostically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from alchemist.autonomy.onboard import c_to_rust_scalar


@dataclass
class Global:
    name: str
    c_type: str
    rust_type: str
    array_len: int | None
    init: str


def _depth0(src: str) -> str:
    """Only the characters at brace depth 0 — strips function/struct/init bodies so
    what remains is file-scope declarations."""
    out, depth = [], 0
    for ch in src:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


_SKIP = ("typedef", "struct", "enum", "union", "extern", "#", "return", "}")


def detect_globals(src: str, defines: dict[str, int] | None = None) -> list[Global]:
    """File-scope mutable globals/statics (the implicit state effectful C carries).
    Skips typedefs, prototypes (contain `(`), consts, and struct/enum defs."""
    defines = defines or {}
    out: list[Global] = []
    for stmt in _depth0(src).split(";"):
        s = re.sub(r"//.*", "", stmt).strip()
        if not s or "(" in s or s.startswith(_SKIP) or "const" in s.split("=")[0]:
            continue
        m = re.match(r"(?:static\s+)?((?:unsigned\s+|signed\s+)*[A-Za-z_]\w*"
                     r"(?:\s+(?:int|long|char|short))*)\s+(\w+)\s*"
                     r"(?:\[\s*(\w+)\s*\])?\s*(?:=\s*(.+))?$", s)
        if not m:
            continue
        c_type, name, dim, init = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
        if c_type in ("void",) or not c_type:
            continue
        n = None
        if dim is not None:
            n = int(dim) if dim.isdigit() else defines.get(dim, 0)
        out.append(Global(name, c_type, c_to_rust_scalar(c_type), n, (init or "").strip()))
    return out


def emit_c_footprint_dump(globals_: list[Global], stream: str = "stdout") -> str:
    """C statements that append every global's raw bytes to the footprint stream."""
    lines = []
    for g in globals_:
        if g.array_len is not None:
            lines.append("fwrite(%s, sizeof(%s), 1, %s);" % (g.name, g.name, stream))
        else:
            lines.append("fwrite(&%s, sizeof(%s), 1, %s);" % (g.name, g.name, stream))
    return "\n  ".join(lines)


def emit_rust_state_struct(globals_: list[Global], name: str = "GlobalState") -> str:
    """Rust struct making the C globals explicit + a matching footprint dumper."""
    fields, defaults, dumps = [], [], []
    for g in globals_:
        if g.array_len is not None:
            fields.append("    pub %s: [%s; %d]," % (g.name, g.rust_type, g.array_len))
            defaults.append("%s: [0; %d]" % (g.name, g.array_len))
            dumps.append("for v in self.%s.iter() { out.extend_from_slice(&v.to_ne_bytes()); }" % g.name)
        else:
            fields.append("    pub %s: %s," % (g.name, g.rust_type))
            defaults.append("%s: %s" % (g.name, g.init or "0"))
            dumps.append("out.extend_from_slice(&self.%s.to_ne_bytes());" % g.name)
    return (
        "#[derive(Clone)]\npub struct %s {\n%s\n}\n"
        "impl Default for %s {\n    fn default() -> Self { Self { %s } }\n}\n"
        "impl %s {\n    pub fn footprint(&self) -> Vec<u8> {\n        let mut out = Vec::new();\n"
        "        %s\n        out\n    }\n}\n"
        % (name, "\n".join(fields), name, ", ".join(defaults), name, "\n        ".join(dumps)))
