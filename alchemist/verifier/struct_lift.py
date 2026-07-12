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


_SCALAR_TYPEDEF_RE = re.compile(
    r"\btypedef\s+([A-Za-z_][\w ]*?)\s+([A-Za-z_]\w*)\s*;")
_TYPEDEF_NONLIB = {"test", "tests", "example", "examples", "bench", "benches",
                   "fuzz", "doc", "docs", "build", "vendor", "third_party",
                   ".git", ".alchemist"}


def collect_scalar_typedefs(c_source_dir) -> dict[str, str]:
    """Map SCALAR typedef aliases to their base C scalar, e.g. `typedef unsigned
    char BYTE;` -> {"BYTE": "unsigned char"}, `typedef unsigned int WORD;` ->
    {"WORD": "unsigned int"}. Resolved transitively (a typedef of a typedef).

    Only scalar typedefs are kept — the base must resolve via c_scalar_to_rust,
    so struct/pointer/function typedefs are skipped. Without this, any struct
    field or param declared with a library's own integer alias (BYTE/WORD/DWORD/
    uchar/…, ubiquitous in real C) is un-mappable and the state struct silently
    fails to carry, breaking the whole library's skeleton (found on sha256)."""
    root = Path(c_source_dir)
    files = list(root.rglob("*.h")) + list(root.rglob("*.c"))
    raw: dict[str, str] = {}
    for cf in sorted(files):
        if {p.lower() for p in cf.relative_to(root).parts[:-1]} & _TYPEDEF_NONLIB:
            continue
        try:
            text = _strip_comments(cf.read_text(errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        for m in _SCALAR_TYPEDEF_RE.finditer(text):
            base = re.sub(r"\s+", " ", m.group(1).strip())
            alias = m.group(2)
            if alias and alias != base:
                raw.setdefault(alias, base)
    out: dict[str, str] = {}
    for alias, base in raw.items():
        seen: set[str] = set()
        b = base
        while b in raw and b not in seen:
            seen.add(b)
            b = raw[b]
        if c_scalar_to_rust(b) is not None:
            out[alias] = b
    return out


_ENUM_TYPEDEF_RE = re.compile(
    r"\btypedef\s+enum\s+(?:\w+\s*)?\{[^{}]*\}\s*([A-Za-z_]\w*)\s*;", re.DOTALL)


def collect_enum_typedefs(c_source_dir) -> dict[str, str]:
    """Map `typedef enum {...} NAME;` aliases to the enum's underlying C integer
    (`int`). A C enum is int-sized, so a struct field typed with the alias (jsmn's
    `jsmntok_t.type: jsmntype_t`) carries as an i32 instead of failing to map."""
    root = Path(c_source_dir)
    files = list(root.rglob("*.h")) + list(root.rglob("*.c"))
    out: dict[str, str] = {}
    for cf in sorted(files):
        if {p.lower() for p in cf.relative_to(root).parts[:-1]} & _TYPEDEF_NONLIB:
            continue
        try:
            text = _strip_comments(cf.read_text(errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        for m in _ENUM_TYPEDEF_RE.finditer(text):
            out[m.group(1)] = "int"
    return out


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
    """Return (body-between-braces, index-of-closing-brace) for the `{` at open_idx.

    Routes through the token-aware `scrubber.find_matching_brace` so braces
    inside string/char literals and comments in the struct body are skipped
    correctly. On an unmatched brace, falls back to consuming to end-of-text
    (preserving this helper's original contract).
    """
    from alchemist.implementer.scrubber import find_matching_brace
    close = find_matching_brace(text, open_idx)
    if close == -1:
        return text[open_idx + 1:], len(text)
    return text[open_idx + 1:close], close


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
    # Drop preprocessor directive lines inside the struct body. A conditional
    # field like `#ifdef JSMN_PARENT_LINKS\n int parent;\n#endif` otherwise
    # glues the directive into the field's ctype ("#ifdef JSMN_PARENT_LINKS int").
    # Removing the `#...` lines keeps the field itself (the common/default build),
    # which is the safe choice for a state struct that must compile.
    body = re.sub(r"(?m)^\s*#.*$", " ", body)
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
    root = Path(c_source_dir)
    _NONLIB = {"test", "tests", "example", "examples", "bench", "benches", "fuzz",
               "doc", "docs", "build", "vendor", "third_party", ".git", ".alchemist"}
    # Resolve the library's own scalar typedefs (BYTE/WORD/…) AND enum typedefs
    # (jsmntype_t → int) so struct fields declared with them map to a Rust scalar
    # instead of silently failing to carry the whole state struct.
    tdefs = collect_scalar_typedefs(c_source_dir)
    tdefs.update(collect_enum_typedefs(c_source_dir))
    # Structs can live in headers or .c files, possibly in subdirs of a real library.
    files = list(root.rglob("*.h")) + list(root.rglob("*.c"))
    for cf in sorted(files):
        if {p.lower() for p in cf.relative_to(root).parts[:-1]} & _NONLIB:
            continue
        try:
            text = cf.read_text(errors="replace")
        except Exception:  # noqa: BLE001
            continue
        for nm in all_struct_names(text):
            f = parse_struct(text, nm)
            if f:
                for fld in f:
                    if fld.ctype in tdefs:
                        fld.ctype = tdefs[fld.ctype]
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


_RUST_KEYWORDS = {
    "as", "break", "const", "continue", "crate", "dyn", "else", "enum", "extern",
    "false", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod", "move",
    "mut", "pub", "ref", "return", "self", "Self", "static", "struct", "super",
    "trait", "true", "type", "unsafe", "use", "where", "while", "async", "await",
    "box", "final", "macro", "override", "priv", "typeof", "unsized", "virtual",
    "yield", "abstract", "become", "do",
}


def _safe_field_name(name: str) -> str:
    """A C field name that is a Rust keyword (`type`, `match`, …) needs a raw
    identifier (`r#type`) or the emitted struct won't compile."""
    return f"r#{name}" if name in _RUST_KEYWORDS else name


def emit_ffi_struct(rust_name: str, fields) -> str | None:
    """Emit a #[repr(C)] mirror struct. Returns None if any field type is unmappable."""
    lines = ["#[repr(C)]", "#[derive(Clone, Copy)]", f"pub struct {rust_name} {{"]
    for f in fields:
        t = f.rust_ffi
        if t is None:
            return None
        lines.append(f"    pub {_safe_field_name(f.name)}: {t},")
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
        fname = _safe_field_name(f.name)
        body.append(f"    pub {fname}: {t},")
        dv = _default_expr(f)
        if dv is None:
            return None
        defaults.append(f"{fname}: {dv}")
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
    "cannot find type Rc4State" wall). The emitted Rust name is whatever the spec's first
    (state) parameter uses — the model may name `bump_alloc`'s state `BumpAllocator`, not the
    computed `BumpAlloc` — mapped to the C struct via the function's struct-pointer param."""
    from alchemist.extractor.schemas import SharedType
    from alchemist.verifier.auto_config import collect_subject_signatures  # lazy: avoid cycle
    structs = structs_in_dir(c_source_dir)
    if not structs:
        return 0
    sigs = {s.name: s for s in collect_subject_signatures(c_source_dir)}
    struct_ptr = re.compile(r"^(?:struct\s+)?([A-Za-z_]\w*)\s*\*$")
    added = 0
    for module in specs:
        present = {t.name for t in (getattr(module, "shared_types", None) or [])}
        # rust_name -> (c_struct_name, fields), keyed on how the SPEC names the state type
        want: dict[str, tuple] = {}
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            if sig is None or not sig.params or not alg.inputs:
                continue
            m = struct_ptr.match((sig.params[0][1] or "").strip())
            if not m or m.group(1) not in structs:
                continue
            # Single-scalar structs are unwrapped to a bare `&mut <primitive>` (e.g.
            # xorshift_state -> &mut u64). Do NOT emit a struct — the spec's "type name"
            # is the primitive itself, and `struct u64 { state: u64 }` shadows + recurses.
            if single_scalar_field(structs[m.group(1)]) is not None:
                continue
            rust_name = (alg.inputs[0].rust_type or "").replace("&mut", "").replace("&", "").strip()
            if not rust_name or not (rust_name[0].isalpha() or rust_name[0] == "_"):
                continue
            want.setdefault(rust_name, (m.group(1), structs[m.group(1)]))
        for rust_name, (cn, fields) in want.items():
            if rust_name in present:
                continue
            definition = emit_safe_struct(rust_name, fields)
            if definition is None:
                continue
            module.shared_types = list(getattr(module, "shared_types", None) or []) + [
                SharedType(
                    name=rust_name,
                    rust_definition=definition,
                    description=f"State struct for C `{cn}` (lifted from source).",
                    fields=[],
                )
            ]
            present.add(rust_name)
            added += 1
    return added


def normalize_single_scalar_state(c_source_dir, specs) -> int:
    """The extractor is inconsistent about single-scalar state structs — some functions keep
    the struct name (`&mut FnvState`), others unwrap to the primitive (`&mut u32`). That
    breaks state sharing (different types) and leaves the struct name undefined. Force ALL
    functions taking a single-scalar struct pointer to the same `&mut <primitive>` (or
    `&<primitive>` for a const pointer). Mutates alg.inputs[*].rust_type; returns count fixed."""
    from alchemist.verifier.auto_config import collect_subject_signatures
    structs = structs_in_dir(c_source_dir)
    single = {}
    for cn, fields in structs.items():
        prim = single_scalar_field(fields)
        if prim is not None:
            single[cn] = prim
    if not single:
        return 0
    try:
        sigs = {s.name: s for s in collect_subject_signatures(c_source_dir)}
    except Exception:  # noqa: BLE001
        return 0
    struct_ptr = re.compile(r"^(const\s+)?(?:struct\s+)?([A-Za-z_]\w*)\s*\*$")
    fixed = 0
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            if sig is None:
                continue
            for i, (_pn, pt) in enumerate(sig.params):
                m = struct_ptr.match((pt or "").strip())
                if not m or m.group(2) not in single:
                    continue
                prim = single[m.group(2)]
                want = f"&{prim}" if m.group(1) else f"&mut {prim}"
                if i < len(alg.inputs or []) and alg.inputs[i].rust_type != want:
                    alg.inputs[i].rust_type = want
                    fixed += 1
    return fixed
