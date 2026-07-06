"""WS2 (prototype): infer the coherent owned-Rust type model from a C struct.

The single biggest per-library cost is deciding how a C pointer graph becomes an
owned Rust type: which pointers are owned buffers (`Vec<T>`), which are back-
references (a `state` pointing at its owning `stream`), which are sub-structs,
which fields are plain scalars, and what the Rust field types are. On zlib a
human made every one of these calls. This module makes the mechanical majority
of them from the struct definition alone, and *flags* the ones that need review
(aliasing, ambiguous ownership) rather than guessing silently.

It is deliberately a first cut: rule-based classification + name/type heuristics,
grounded in and validated against the zlib hand-model. It is NOT a full pointer
analysis — genuine aliasing detection (two fields naming the same memory) needs
usage/flow analysis and is surfaced as a review flag, not decided here.

See docs/PATH_TO_AUTONOMY.md (WS2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from alchemist.autonomy.c_struct import _find_struct_body

# C scalar type -> Rust scalar. Sizes/indices are resolved to usize by heuristic
# below, not here (a `uInt` used as a length is usize; as a flag it's u32).
_SCALAR: dict[str, str] = {
    "int": "i32", "signed": "i32", "unsigned": "u32", "unsigned int": "u32",
    "uInt": "u32", "uint": "u32",
    "long": "i64", "unsigned long": "u64", "ulg": "u64", "uLong": "u64",
    "short": "i16", "unsigned short": "u16", "ush": "u16",
    "Pos": "u16", "Posf": "u16", "IPos": "u32",
    "char": "i8", "signed char": "i8", "unsigned char": "u8",
    "Byte": "u8", "Bytef": "u8", "uch": "u8", "uchf": "u8",
    "size_t": "usize", "ptrdiff_t": "isize",
    "int8_t": "i8", "uint8_t": "u8", "int16_t": "i16", "uint16_t": "u16",
    "int32_t": "i32", "uint32_t": "u32", "int64_t": "i64", "uint64_t": "u64",
    "z_off_t": "i64", "z_off64_t": "i64", "z_word_t": "u64", "z_crc_t": "u32",
}

# Rust keywords that a C field name can collide with -> raw identifier `r#name`
_RUST_KEYWORDS = frozenset(
    "as break const continue crate dyn else enum extern false fn for if impl in "
    "let loop match mod move mut pub ref return self Self static struct super trait "
    "true type unsafe use where while async await box do final macro override priv "
    "typeof unsized virtual yield".split()
)


def rust_ident(name: str) -> str:
    """Escape a C field name that collides with a Rust keyword (`type` -> `r#type`)."""
    return f"r#{name}" if name in _RUST_KEYWORDS else name


# fields whose name strongly implies a size/index/count -> usize in Rust
_INDEXISH = re.compile(
    r"(?:_size|_len|_length|start|pos|index|_bits$|head|tail|next|max$|"
    r"strstart|lookahead|_mask|_shift|whave|wnext|wsize|wbits)", re.IGNORECASE
)
# a pointer/typedef that points back at the owning stream/parent
_BACKPTR = re.compile(r"stream|strm|z_streamp|internal_state|parent|owner", re.IGNORECASE)


@dataclass
class FieldModel:
    name: str
    c_type: str          # base type tokens as written
    ptr: int             # pointer depth
    array: str | None    # array dimension text, if any
    kind: str            # scalar | buffer | array | back_ptr | sub_struct | opaque
    rust_type: str
    rationale: str
    review: bool = False  # True => a human should confirm (ownership/aliasing risk)


@dataclass
class StructModel:
    name: str
    fields: list[FieldModel] = dc_field(default_factory=list)
    buffer_pairs: list[tuple[str, str]] = dc_field(default_factory=list)  # (ptr, len)
    notes: list[str] = dc_field(default_factory=list)

    def review_fields(self) -> list[FieldModel]:
        return [f for f in self.fields if f.review]

    def render(self) -> str:
        lines = [f"struct {self.name} (inferred):"]
        for f in self.fields:
            flag = "  ⚠review" if f.review else ""
            lines.append(f"  {f.name}: {f.rust_type}    // {f.kind}: {f.rationale}{flag}")
        if self.buffer_pairs:
            lines.append("  buffer (ptr,len) pairs: " + ", ".join(f"{p}/{l}" for p, l in self.buffer_pairs))
        return "\n".join(lines)

    def render_rust(self) -> str:
        """Emit the inferred coherent Rust struct definition."""
        out = [f"#[derive(Clone, Default)]", f"pub struct {self.name} {{"]
        for f in self.fields:
            if f.kind == "back_ptr":
                out.append(f"    // {f.name}: back-reference to the owning stream — modeled by ownership, omitted")
                continue
            note = "  // ⚠ review" if f.review else ""
            out.append(f"    pub {rust_ident(f.name)}: {f.rust_type},{note}")
        out.append("}")
        return "\n".join(out)


def _scalar_rust(c_type: str, name: str) -> str:
    base = _SCALAR.get(c_type, _SCALAR.get(c_type.replace("f", ""), None))
    if base is None:
        return "u32"  # conservative default for unknown integer typedefs
    # size/index-ish integers become usize (matches the zlib coherent model:
    # strstart/lookahead/*_size are usize, flags/levels stay u32/i32)
    if base in ("u32", "u64", "i64") and _INDEXISH.search(name):
        return "usize"
    return base


def _parse_detailed(source: str, struct_name: str) -> list[tuple[str, str, int, str | None]]:
    """(name, base_type, ptr_depth, array_dim) for each field — keeps * and []."""
    body = _find_struct_body(source, struct_name)
    if body is None:
        return []
    body = re.sub(r"\{[^{}]*\}", " ", body)  # drop inline union/struct groups
    body = re.sub(r"^\s*#.*$", "", body, flags=re.MULTILINE)  # drop preprocessor lines
    out: list[tuple[str, str, int, str | None]] = []
    for stmt in body.split(";"):
        stmt = stmt.strip()
        if not stmt or stmt.startswith(("#", "//")):
            continue
        arr = None
        am = re.search(r"\[([^\]]*)\]", stmt)
        if am:
            arr = am.group(1).strip()
            stmt = re.sub(r"\[[^\]]*\]", "", stmt)
        # split comma declarators; each shares the base type of the first
        parts = [p.strip() for p in stmt.split(",") if p.strip()]
        first = parts[0]
        ptr = first.count("*")
        toks = first.replace("*", " ").split()
        if len(toks) < 2:
            continue
        name = toks[-1]
        base = " ".join(toks[:-1])
        if re.fullmatch(r"[A-Za-z_]\w*", name):
            out.append((name, base, ptr, arr))
        for extra in parts[1:]:
            p2 = extra.count("*")
            t2 = extra.replace("*", " ").split()
            if t2 and re.fullmatch(r"[A-Za-z_]\w*", t2[-1]):
                out.append((t2[-1], base, p2, arr))
    return out


def classify_field(name: str, base: str, ptr: int, array: str | None,
                   known_structs: set[str]) -> FieldModel:
    is_struct = base in known_structs or base.startswith("struct ") or base.endswith("_s") \
        or base.endswith("_state") or base in ("z_stream",)
    elem = _SCALAR.get(base)

    # A back-reference to the owning stream/parent. `z_streamp` etc. are pointer
    # typedefs (ptr depth 0 in the decl but still a pointer), so match on the
    # TYPE NAME, not just an explicit `*`.
    if _BACKPTR.search(base) or (ptr and _BACKPTR.search(name)):
        return FieldModel(name, base, ptr, array, "back_ptr", "()  /* back-ref: owned by the stream */",
                          "pointer back to the owning stream/parent — not owned here", review=True)
    if array is not None and elem:
        return FieldModel(name, base, ptr, array, "array", f"Vec<{elem}>",
                          f"fixed C array [{array}] of {base} -> owned Vec")
    if array is not None and is_struct:
        rn = _rust_struct_name(base)
        return FieldModel(name, base, ptr, array, "array", f"Vec<{rn}>",
                          f"array of sub-struct {base} -> owned Vec")
    if ptr and elem:
        return FieldModel(name, base, ptr, array, "buffer", f"Vec<{elem}>",
                          f"{base}* buffer -> owned Vec (was ptr+len)")
    if ptr and is_struct:
        rn = _rust_struct_name(base)
        return FieldModel(name, base, ptr, array, "sub_struct", rn,
                          f"pointer to sub-struct {base} -> owned by value",
                          review=True)
    if is_struct:
        rn = _rust_struct_name(base)
        return FieldModel(name, base, ptr, array, "sub_struct", rn,
                          f"embedded sub-struct {base} -> owned by value")
    if ptr:
        return FieldModel(name, base, ptr, array, "opaque", "()",
                          f"opaque pointer ({base}*) — needs review", review=True)
    return FieldModel(name, base, ptr, array, "scalar", _scalar_rust(base, name),
                      f"scalar {base}")


def _rust_struct_name(c_name: str) -> str:
    n = re.sub(r"^struct\s+", "", c_name).rstrip("_")
    n = n[:-2] if n.endswith("_s") else n
    return "".join(p.capitalize() for p in n.split("_")) or "Sub"


def infer_struct_model(source: str, struct_name: str,
                       known_structs: set[str] | None = None) -> StructModel:
    known = known_structs or set()
    fields = _parse_detailed(source, struct_name)
    model = StructModel(_rust_struct_name(struct_name))
    names = {n for n, *_ in fields}
    for name, base, ptr, array in fields:
        model.fields.append(classify_field(name, base, ptr, array, known))
    # detect ptr+len buffer pairs: a buffer field X with a sibling X_size/X_len
    for f in model.fields:
        if f.kind == "buffer":
            for cand in (f.name + "_size", f.name + "_len", f.name + "size",
                         f.name + "_length"):
                if cand in names:
                    model.buffer_pairs.append((f.name, cand))
                    break
    if any(f.review for f in model.fields):
        model.notes.append("fields flagged ⚠review need a human/usage-analysis call "
                           "(ownership direction, aliasing, opaque pointers).")
    return model
