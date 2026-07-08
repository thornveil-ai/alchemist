"""Parse C ``struct`` definitions and map their fields to Rust.

Tracked, dependency-free replacement for the retired ``autonomy/`` struct lifter.
Used by the stateful differential shapes in :mod:`alchemist.verifier.auto_config`
to (a) recognise a struct-pointer-first stateful function and (b) emit the
``#[repr(C)]`` FFI mirror struct so the compiled-C reference can be driven from Rust.
"""
from __future__ import annotations

import re
from pathlib import Path

_ARR_RE = re.compile(r"\[\s*(\w+)\s*\]")

# C scalar type -> Rust type (LP64 / Linux x86-64, which is where the oracle builds).
_SCALAR = {
    "unsigned long long": "u64", "long long": "i64",
    "unsigned long": "u64", "long": "i64",
    "unsigned int": "u32", "int": "i32", "unsigned": "u32",
    "unsigned short": "u16", "short": "i16",
    "unsigned char": "u8", "signed char": "i8", "char": "u8",
    "uint8_t": "u8", "int8_t": "i8", "uint16_t": "u16", "int16_t": "i16",
    "uint32_t": "u32", "int32_t": "i32", "uint64_t": "u64", "int64_t": "i64",
    "size_t": "usize", "ssize_t": "isize", "float": "f32", "double": "f64",
}


def c_scalar_to_rust(ctype: str) -> str | None:
    return _SCALAR.get((ctype or "").strip())


class Field:
    def __init__(self, name: str, ctype: str, arr, is_ptr: bool):
        self.name = name
        self.ctype = ctype
        self.arr = arr            # int, symbolic str, or None
        self.is_ptr = is_ptr

    @property
    def rust_ffi(self) -> str | None:
        """The #[repr(C)] field type. Pointers stay raw; unknown scalars fail (None)."""
        if self.is_ptr:
            base = c_scalar_to_rust(self.ctype) or "u8"
            return f"*mut {base}"
        base = c_scalar_to_rust(self.ctype)
        if base is None:
            return None
        if self.arr is not None:
            return f"[{base}; {self.arr}]"
        return base


def _strip_comments(t: str) -> str:
    t = re.sub(r"/\*.*?\*/", " ", t, flags=re.DOTALL)
    t = re.sub(r"//[^\n]*", " ", t)
    return t


def _matching_brace_body(text: str, open_idx: int) -> tuple[str, int]:
    depth = 0
    j = open_idx
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:j], j
        j += 1
    return text[open_idx + 1:], len(text)


def _find_body(text: str, name: str) -> str | None:
    text = _strip_comments(text)
    # typedef struct [tag] { BODY } NAME ;
    for m in re.finditer(r"typedef\s+struct\s+(?:\w+\s*)?\{", text):
        i = text.index("{", m.start())
        body, j = _matching_brace_body(text, i)
        tm = re.match(r"\s*(\w+)\s*;", text[j + 1:])
        if tm and tm.group(1) == name:
            return body
    # struct NAME { BODY } ;
    m = re.search(r"struct\s+" + re.escape(name) + r"\s*\{", text)
    if m:
        i = text.index("{", m.start())
        body, _ = _matching_brace_body(text, i)
        return body
    return None


def parse_struct(text: str, name: str) -> list[Field] | None:
    body = _find_body(text, name)
    if body is None:
        return None
    fields: list[Field] = []
    for decl in body.split(";"):
        decl = decl.strip()
        if not decl:
            continue
        arr = None
        am = _ARR_RE.search(decl)
        if am:
            dim = am.group(1)
            arr = int(dim) if dim.isdigit() else dim
            decl = (decl[:am.start()] + decl[am.end():]).strip()
        is_ptr = "*" in decl
        decl = decl.replace("*", " ")
        parts = decl.split()
        if len(parts) < 2:
            continue
        fields.append(Field(parts[-1], " ".join(parts[:-1]), arr, is_ptr))
    return fields


def all_struct_names(text: str) -> list[str]:
    text = _strip_comments(text)
    names: list[str] = []
    for m in re.finditer(r"typedef\s+struct\s+(?:\w+\s*)?\{[^{}]*\}\s*(\w+)\s*;", text, re.DOTALL):
        names.append(m.group(1))
    for m in re.finditer(r"struct\s+(\w+)\s*\{", text):
        names.append(m.group(1))
    return names


def structs_in_dir(c_source_dir) -> dict[str, list[Field]]:
    out: dict[str, list[Field]] = {}
    for cf in sorted(Path(c_source_dir).glob("*.c")):
        try:
            text = cf.read_text()
        except Exception:  # noqa: BLE001
            continue
        for nm in all_struct_names(text):
            f = parse_struct(text, nm)
            if f:
                out.setdefault(nm, f)
    return out


def single_scalar_field(fields) -> str | None:
    """If the struct is exactly one non-pointer, non-array scalar, return its Rust type."""
    if not fields or len(fields) != 1:
        return None
    f = fields[0]
    if f.is_ptr or f.arr is not None:
        return None
    return c_scalar_to_rust(f.ctype)


def emit_ffi_struct(rust_name: str, fields) -> str | None:
    """Emit a #[repr(C)] mirror struct. Returns None if any field type is unmappable."""
    lines = ["#[repr(C)]", "#[derive(Clone, Copy)]", f"pub struct {rust_name} {{"]
    for f in fields:
        t = f.rust_ffi
        if t is None:
            return None
        lines.append(f"    pub {f.name}: {t},")
    lines.append("}")
    return "\n".join(lines) + "\n"


def rust_struct_name(c_name: str) -> str:
    """rc4_state -> Rc4State, xorshift_state -> XorshiftState (the extractor's convention)."""
    return "".join(p[:1].upper() + p[1:].lower() for p in c_name.split("_") if p)


def _default_expr(f: "Field") -> str | None:
    base = c_scalar_to_rust(f.ctype)
    if base is None:
        return None
    zero = "0.0" if base in ("f32", "f64") else "0"
    if f.arr is not None:
        return f"[{zero}; {f.arr}]"
    return zero


def pointer_field_names(fields) -> list[str]:
    """Raw-pointer field names — dropped from the safe struct; the model must not set them."""
    return [f.name for f in (fields or []) if f.is_ptr]


def emit_safe_struct(rust_name: str, fields) -> str | None:
    """Emit a SAFE (non-repr-C) struct + Default. Raw-pointer fields are DROPPED — a borrowed
    or raw buffer pointer has no faithful safe field, and stateful logic that only tracks
    scalar offsets/indices doesn't observe it. Returns None if no representable field remains
    or a non-pointer scalar is unmappable."""
    body, defaults, dropped = [], [], []
    for f in fields:
        if f.is_ptr:
            dropped.append(f.name)
            continue
        base = c_scalar_to_rust(f.ctype)
        if base is None:
            return None
        t = f"[{base}; {f.arr}]" if f.arr is not None else base
        body.append(f"    pub {f.name}: {t},")
        dv = _default_expr(f)
        if dv is None:
            return None
        defaults.append(f"{f.name}: {dv}")
    if not body:
        return None
    note = ""
    if dropped:
        note = ("// Raw-pointer field(s) dropped (no safe representation; not observed by the\n"
                "// scalar state logic): " + ", ".join(dropped) + "\n")
    struct = note + "#[derive(Clone)]\npub struct " + rust_name + " {\n" + "\n".join(body) + "\n}\n"
    fields_init = ", ".join(defaults)
    dflt = (
        f"impl Default for {rust_name} {{\n"
        f"    fn default() -> Self {{ Self {{ {fields_init} }} }}\n"
        f"}}\n"
    )
    return struct + dflt


def inject_state_shared_types(c_source_dir, specs) -> int:
    """For each module, emit a SharedType for any struct referenced by a function param
    (as `&mut RustName`, `&RustName`, `RustName`) that isn't already defined, using the C
    struct as the source of truth. Mutates ``module.shared_types``; returns count added.

    This is the struct-carry that lets the skeleton compile stateful code cold (kills the
    "cannot find type Rc4State" wall)."""
    from alchemist.extractor.schemas import SharedType
    structs = structs_in_dir(c_source_dir)
    by_rust = {rust_struct_name(cn): (cn, f) for cn, f in structs.items()}
    if not by_rust:
        return 0
    added = 0
    for module in specs:
        present = {t.name for t in (getattr(module, "shared_types", None) or [])}
        referenced: set[str] = set()
        for alg in getattr(module, "algorithms", None) or []:
            for inp in (alg.inputs or []):
                for tok in re.findall(r"[A-Za-z_]\w*", inp.rust_type or ""):
                    if tok in by_rust:
                        referenced.add(tok)
        for rn in sorted(referenced):
            if rn in present:
                continue
            cn, fields = by_rust[rn]
            definition = emit_safe_struct(rn, fields)
            if definition is None:
                continue
            module.shared_types = list(getattr(module, "shared_types", None) or []) + [
                SharedType(
                    name=rn,
                    rust_definition=definition,
                    description=f"State struct for C `{cn}` (lifted from source).",
                    fields=[],
                )
            ]
            present.add(rn)
            added += 1
    return added
