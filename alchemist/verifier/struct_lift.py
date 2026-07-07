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
