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


_STRUCT_TYPEDEF_RE = re.compile(r"\btypedef\s+struct\s+(\w+)\s+(\w+)\s*;")


def collect_struct_typedefs(c_source_dir) -> dict[str, str]:
    """`typedef struct TAG ALIAS;` -> {ALIAS: TAG}. An OPAQUE / forward-typedef'd struct
    (parson: `typedef struct json_value_t JSON_Value;`) declares the struct as its TAG
    separately (no inline `{...}` body), so all_struct_names keys only the tag — but every
    signature uses the ALIAS. Without this mapping, a `JSON_Value*`/`JSON_Object*` param or
    return is an UNKNOWN type, so it's never canonicalized or emitted (E0425 on the whole
    crate). Matches the alias-of-existing-tag form only (the inline-def form has a `{`)."""
    out: dict[str, str] = {}
    root = Path(c_source_dir)
    for cf in sorted(list(root.rglob("*.h")) + list(root.rglob("*.c"))):
        try:
            text = _strip_comments(cf.read_text(errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        for m in _STRUCT_TYPEDEF_RE.finditer(text):
            tag, alias = m.group(1), m.group(2)
            if alias != tag:
                out.setdefault(alias, tag)
    return out


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
    # Alias opaque/forward-typedef'd structs to their fields, so `JSON_Value`
    # (the name every signature uses) resolves to `struct json_value_t`'s fields.
    for alias, tag in collect_struct_typedefs(c_source_dir).items():
        if tag in out and alias not in out:
            out[alias] = out[tag]
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


# Struct-pointer field names that read as a COUNTED ARRAY of children (JSON array,
# n-ary tree) when the struct also carries a length scalar -> lift to `Vec<T>`.
_ARRAYISH_PTR_NAMES = {
    "items", "elements", "children", "entries", "data", "values", "keys",
    "array", "arr", "nodes", "cells", "members", "tokens", "list", "buckets",
}
# Scalar field names that read as the length of a sibling array pointer.
_COUNT_FIELD_NAMES = {
    "count", "size", "len", "length", "n", "num", "nmemb", "capacity",
    "cap", "used", "nitems", "ntokens", "nmemb", "nkeys", "nvalues",
}


def _pointee_c_name(f: "Field") -> str:
    """The C struct a pointer field points at: `struct node *` -> `node`, `Node *` -> `Node`."""
    return re.sub(r"^(?:const\s+)?struct\s+", "", (f.ctype or "").strip())


def emit_safe_struct(rust_name: str, fields, *, c_to_rust: dict | None = None) -> str | None:
    """Emit a SAFE (non-repr-C) struct + Default.

    KEYSTONE #3 (ownership at library scale): a pointer field to ANOTHER CARRIED struct
    is LIFTED to an owned safe form instead of being dropped — `T* next` -> `Option<Box<T>>`
    (single owned child: linked list, binary-tree left/right), or `Vec<T>` when the field
    reads as a counted array and the struct carries a length scalar (JSON array / DOM). This
    is what lets a heap-linked data-structure library's skeleton compile cold. `c_to_rust`
    maps C struct names -> their canonical Rust names (only structs that WILL be emitted, so
    the reference always resolves); pass it from the whole-program canonicalization pass.

    Raw scalar/char buffer pointers (no carried-struct pointee) are still DROPPED — a borrowed
    or raw buffer pointer has no faithful safe field, and scalar offset/index state doesn't
    observe it (rc4/allocators rely on this). Returns None if no representable field remains or
    a non-pointer scalar is unmappable."""
    c_to_rust = c_to_rust or {}
    scalar_names = {f.name for f in fields if not f.is_ptr and f.arr is None}
    has_count = bool(scalar_names & _COUNT_FIELD_NAMES)
    body, defaults, dropped, lifted = [], [], [], []
    for f in fields:
        if f.is_ptr:
            # Self-references are fine: Box breaks the infinite-size cycle.
            rust_pointee = c_to_rust.get(_pointee_c_name(f))
            if rust_pointee:
                fname = _safe_field_name(f.name)
                # alloc-qualified: the emitted struct lives in a no_std crate module that
                # does NOT import Box/Vec (only the crate root does); `extern crate alloc`
                # at the root makes `alloc::...` resolve from any module.
                if f.name in _ARRAYISH_PTR_NAMES and has_count:
                    body.append(f"    pub {fname}: alloc::vec::Vec<{rust_pointee}>,")
                    defaults.append(f"{fname}: alloc::vec::Vec::new()")
                    lifted.append(f"{f.name} -> Vec<{rust_pointee}>")
                else:
                    body.append(f"    pub {fname}: Option<alloc::boxed::Box<{rust_pointee}>>,")
                    defaults.append(f"{fname}: None")
                    lifted.append(f"{f.name} -> Option<Box<{rust_pointee}>>")
                continue
            dropped.append(f.name)
            continue
        base = c_scalar_to_rust(f.ctype)
        dv = _default_expr(f) if base is not None else None
        if base is None or dv is None:
            # Unmappable non-pointer field — a C UNION (parson's JSON_Value_Value:
            # string|number|Object*|Array*|bool), or an unresolved typedef. DROP it rather
            # than fail the WHOLE struct (which would leave it undefined -> E0425 breaks the
            # crate). The struct then compiles; functions that don't touch the field can
            # still verify byte-exact, and any function that DOES depend on it fails the
            # differential and is honestly refused (fail-closed). Proper C-union -> Rust-enum
            # modelling is a separate keystone.
            dropped.append(f.name)
            continue
        t = f"[{base}; {f.arr}]" if f.arr is not None else base
        fname = _safe_field_name(f.name)
        body.append(f"    pub {fname}: {t},")
        defaults.append(f"{fname}: {dv}")
    if not body:
        return None
    note = ""
    if lifted:
        note += ("// Owned pointer field(s) lifted to safe Rust (malloc/free -> Box/Vec): "
                 + ", ".join(lifted) + "\n")
    if dropped:
        note += ("// Field(s) dropped (no faithful safe representation — raw buffer pointer,\n"
                 "// C union, or unresolved type; a fn that depends on one fails the\n"
                 "// differential and is honestly refused): " + ", ".join(dropped) + "\n")
    struct = note + "#[derive(Clone)]\npub struct " + rust_name + " {\n" + "\n".join(body) + "\n}\n"
    fields_init = ", ".join(defaults)
    dflt = (
        f"impl Default for {rust_name} {{\n"
        f"    fn default() -> Self {{ Self {{ {fields_init} }} }}\n"
        f"}}\n"
    )
    return struct + dflt


_RUST_PRIMS = {
    "u8", "i8", "u16", "i16", "u32", "i32", "u64", "i64", "u128", "i128",
    "usize", "isize", "f32", "f64", "bool", "char", "str", "String",
}


def _bare_struct_name(rust_type: str) -> "str | None":
    """Strip container syntax (`Option<`, `&mut`, `&`, `[`, `]`, `Box<`, `>`, ws)
    from a Rust type to the innermost identifier — `Option<&mut [Token]>` -> `Token`,
    `&[u8]` -> `u8`, `&str` -> `str`. Returns None if it isn't a bare identifier."""
    t = re.sub(r"Option<|Box<|Vec<|&mut\b|&|\[|\]|>|\s|;\s*\d+", "", rust_type or "")
    return t if t and (t[0].isalpha() or t[0] == "_") else None


def inject_state_shared_types(c_source_dir, specs) -> int:
    """For each module, emit a SharedType for any struct referenced by a function param
    (as `&mut RustName`, `&RustName`, `RustName`) that isn't already defined, using the C
    struct as the source of truth. Mutates ``module.shared_types``; returns count added.

    This is the struct-carry that lets the skeleton compile stateful code cold (kills the
    "cannot find type Rc4State" wall). The emitted Rust name is whatever the spec's first
    (state) parameter uses — the model may name `bump_alloc`'s state `BumpAllocator`, not the
    computed `BumpAlloc` — mapped to the C struct via the function's struct-pointer param."""
    from collections import Counter, defaultdict
    from alchemist.extractor.schemas import SharedType
    from alchemist.verifier.auto_config import collect_subject_signatures  # lazy: avoid cycle
    # Scalar/enum-typed signature references -> Rust scalar. The extractor sometimes names
    # a C typedef return/param by a Rust TYPE name (`JSON_Value_Type` -> `JsonValueType`)
    # that is never defined -> E0425 breaks the crate. Two forms fracture identically:
    #   * enum typedef (`typedef enum {...} T;`)          -> int-sized -> i32
    #   * scalar typedef (`typedef int JSON_Value_Type;`) -> the base Rust scalar
    # parson is the second form: `enum json_value_type {..}` and `typedef int
    # JSON_Value_Type;` are DECLARED SEPARATELY, so the enum-typedef scan misses the alias
    # entirely. Resolve BOTH via the same rewrite (we already resolve enum/typedef STRUCT
    # FIELDS the same way). Runs even for a subject with NO structs (an enum/typedef-only
    # header still fractures signatures).
    _type_to_scalar: dict[str, str] = {}
    for _alias, _base in collect_scalar_typedefs(c_source_dir).items():
        _rs = c_scalar_to_rust(_base)
        if _rs:
            _type_to_scalar[rust_struct_name(_alias)] = _rs
    for _alias in collect_enum_typedefs(c_source_dir):
        _type_to_scalar.setdefault(rust_struct_name(_alias), "i32")
    if _type_to_scalar:
        for module in specs:
            for alg in getattr(module, "algorithms", None) or []:
                for inp in (alg.inputs or []):
                    b = _bare_struct_name(inp.rust_type)
                    s = _type_to_scalar.get(b)
                    if s:
                        inp.rust_type = re.sub(r"\b" + re.escape(b) + r"\b", s,
                                               inp.rust_type or "")
                rb = _bare_struct_name(getattr(alg, "return_type", "") or "")
                s = _type_to_scalar.get(rb)
                if s:
                    alg.return_type = re.sub(r"\b" + re.escape(rb) + r"\b", s,
                                             alg.return_type or "")
    structs = structs_in_dir(c_source_dir)
    if not structs:
        return 0
    sigs = {s.name: s for s in collect_subject_signatures(c_source_dir)}
    struct_ptr = re.compile(r"^(?:struct\s+)?([A-Za-z_]\w*)\s*\*$")

    def _c_struct_of(inp_name: str, sig) -> "str | None":
        """The C struct a Rust input maps to — matched BY PARAM NAME (positional
        alignment breaks when the extractor folds length params). Skips single-scalar
        structs (those unwrap to a bare primitive, not a carried struct)."""
        by_name = {p[0]: (p[1] or "") for p in sig.params}
        ct = re.sub(r"^const\s+", "", (by_name.get(inp_name) or "").strip())
        m = struct_ptr.match(ct)
        if not m or m.group(1) not in structs:
            return None
        if single_scalar_field(structs[m.group(1)]) is not None:
            return None
        return m.group(1)

    def _c_struct_of_return(sig) -> "str | None":
        """The C struct a function RETURNS a pointer to (`JSON_Value* json_parse_string(...)`
        -> `JSON_Value`). A struct that appears ONLY as a return type (never a param) is
        otherwise invisible to the param-only canonicalization, so it's never emitted."""
        ct = re.sub(r"^const\s+", "", (getattr(sig, "return_type", "") or "").strip())
        m = struct_ptr.match(ct)
        if not m or m.group(1) not in structs:
            return None
        if single_scalar_field(structs[m.group(1)]) is not None:
            return None
        return m.group(1)

    # --- KEYSTONE #1: whole-program type coherence ---------------------------
    # PASS 1 (subject-wide): map each C struct to every Rust name the extractor gave
    # it across ALL functions. The extractor is inconsistent (jsmn's jsmn_parser came
    # out as both `ParserState` and `Parser`), which makes init/parse take DIFFERENT
    # Rust types for the SAME struct — a caller can't share it and the workspace is
    # incoherent. Pick ONE canonical name per C struct and rewrite every signature to it.
    c_to_names: dict[str, Counter] = defaultdict(Counter)
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            if sig is None:
                continue
            for inp in (alg.inputs or []):
                cn = _c_struct_of(inp.name, sig)
                if cn is None:
                    continue
                bare = _bare_struct_name(inp.rust_type)
                if bare and bare not in _RUST_PRIMS:
                    c_to_names[cn][bare] += 1
            # return type — a struct that appears only as a return is otherwise missed
            cr = _c_struct_of_return(sig)
            if cr is not None:
                bret = _bare_struct_name(getattr(alg, "return_type", "") or "")
                if bret and bret not in _RUST_PRIMS:
                    c_to_names[cr][bret] += 1
    # canonical = most-frequent name, tie-break: longer, then alphabetically-later.
    canon_of_c: dict[str, str] = {}
    alias_to_canon: dict[str, str] = {}
    for cn, cnt in c_to_names.items():
        best = max(cnt.items(), key=lambda kv: (kv[1], len(kv[0]), kv[0]))[0]
        canon_of_c[cn] = best
        for name in cnt:
            alias_to_canon[name] = best
    # Unify opaque-typedef ALIAS <-> TAG: `typedef struct json_value_t JSON_Value;`
    # makes them the SAME struct, so they MUST share ONE canonical Rust name — else the
    # self-ref field `struct json_value_t *parent` emits `Option<Box<JsonValueT>>` while
    # every signature uses `JsonValue`, and the crate won't compile. Prefer a signature-
    # derived canon; else the ALIAS's convention name (JSON_Value -> JsonValue, not the
    # tag's JsonValueT).
    for _alias, _tag in collect_struct_typedefs(c_source_dir).items():
        _canon = canon_of_c.get(_alias) or canon_of_c.get(_tag) or rust_struct_name(_alias)
        canon_of_c[_alias] = _canon
        canon_of_c[_tag] = _canon
        alias_to_canon.setdefault(rust_struct_name(_alias), _canon)
        alias_to_canon.setdefault(rust_struct_name(_tag), _canon)

    # PASS 2: rewrite every alg.input.rust_type + return_type alias -> canonical.
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            for inp in (alg.inputs or []):
                bare = _bare_struct_name(inp.rust_type)
                canon = alias_to_canon.get(bare or "")
                if canon and canon != bare:
                    inp.rust_type = re.sub(r"\b" + re.escape(bare) + r"\b",
                                           canon, inp.rust_type or "")
            bret = _bare_struct_name(getattr(alg, "return_type", "") or "")
            rcanon = alias_to_canon.get(bret or "")
            if rcanon and rcanon != bret:
                alg.return_type = re.sub(r"\b" + re.escape(bret) + r"\b",
                                         rcanon, alg.return_type or "")

    # Subject-wide C-struct -> Rust-name map (canonical where known, else the
    # extractor's convention). KEYSTONE #3 uses it to lift a pointer-to-carried-struct
    # field to `Option<Box<Rust>>` / `Vec<Rust>` instead of dropping it.
    c_to_rust = dict(canon_of_c)
    for cn in structs:
        c_to_rust.setdefault(cn, rust_struct_name(cn))

    def _referenced_struct_pointees(fields) -> list:
        """C struct names a struct's POINTER fields point at (that are themselves carried
        structs) — the transitive closure roots for owning linked/tree/DOM data."""
        out = []
        for f in fields:
            if f.is_ptr:
                p = _pointee_c_name(f)
                if p in structs and single_scalar_field(structs[p]) is None:
                    out.append(p)
        return out

    # PASS 3: emit ONE SharedType per canonical struct each module references, PLUS the
    # transitive closure of structs reachable through owned pointer fields (so a linked
    # list / tree / DOM library gets a coherent, compilable skeleton — every node type
    # its owned links reference is defined).
    added = 0
    for module in specs:
        present = {t.name for t in (getattr(module, "shared_types", None) or [])}
        want: dict[str, tuple] = {}  # rust_name -> (c_struct, fields)
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            if sig is None:
                continue
            for inp in (alg.inputs or []):
                cn = _c_struct_of(inp.name, sig)
                if cn is None:
                    continue
                canon = canon_of_c.get(cn)
                if canon and (canon[0].isalpha() or canon[0] == "_"):
                    want.setdefault(canon, (cn, structs[cn]))
            cr = _c_struct_of_return(sig)
            if cr is not None:
                canon = canon_of_c.get(cr)
                if canon and (canon[0].isalpha() or canon[0] == "_"):
                    want.setdefault(canon, (cr, structs[cr]))
        # transitive closure over owned pointer fields
        queue = list(want.values())
        while queue:
            _cn, _fields = queue.pop()
            for p in _referenced_struct_pointees(_fields):
                rn = c_to_rust.get(p)
                if rn and rn not in want and (rn[0].isalpha() or rn[0] == "_"):
                    want[rn] = (p, structs[p])
                    queue.append((p, structs[p]))
        for rust_name, (cn, fields) in want.items():
            if rust_name in present:
                continue
            definition = emit_safe_struct(rust_name, fields, c_to_rust=c_to_rust)
            if definition is None:
                continue
            module.shared_types = list(getattr(module, "shared_types", None) or []) + [
                SharedType(
                    name=rust_name,
                    rust_definition=definition,
                    description=f"State struct for C `{cn}` (lifted from source, canonical name).",
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
