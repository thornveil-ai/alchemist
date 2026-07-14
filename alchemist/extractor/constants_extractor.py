"""C `#define` / `enum` / `static const` → Rust `pub const` auto-extractor.

Phase 1a goal: remove the entire class of LLM failures caused by the
model hallucinating or truncating long precomputed tables (CRC32_TABLE,
POLY, BASE, NMAX, etc.). Every named compile-time constant in the C
source is lifted deterministically into Rust and injected as a `pub
const` at the matching module, alongside the functions that use it.

Three extractor backends:

  1. `#define NAME VALUE` — simple macro values. Recognized for:
     - Integer literals (decimal, hex, binary, octal)
     - Simple integer expressions (shifts, bitwise, arithmetic)
     - Character literals ('A')
     - String literals ("..." — emitted as `&'static str` or `&[u8]`)
     - References to previously-extracted constants

  2. `enum { A = 1, B, C = 0x10, ... }` — C enum values. Emitted as
     individual `pub const` (we avoid a full Rust enum on purpose:
     C enums allow arithmetic, which Rust enums don't).

  3. `static const TYPE NAME[...] = { ... };` — precomputed tables.
     This is the critical case (LLM can't reliably reproduce them).

Macros with arguments (`#define FOO(x) ...`) are ignored — they're not
constants. The LLM path handles those.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from alchemist.extractor.schemas import ConstantSpec


# ---------------------------------------------------------------------------
# C preprocessor — bare-bones, good enough for common constant patterns
# ---------------------------------------------------------------------------

_DEFINE_RE = re.compile(
    r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+([^\n\\]*(?:\\\n[^\n\\]*)*)\s*$",
    re.MULTILINE,
)
_DEFINE_FN_LIKE_RE = re.compile(r"^\s*#\s*define\s+[A-Za-z_]\w*\s*\(", re.MULTILINE)

_ENUM_BLOCK_RE = re.compile(
    r"\benum\s+(?:[A-Za-z_]\w*\s+)?\{([^}]*)\}\s*;", re.MULTILINE | re.DOTALL,
)

# Match `static const <type> NAME [<dims>] = { ... } ;` with nested braces.
# We locate the start and then walk to the matching closing brace.
_STATIC_CONST_RE = re.compile(
    r"(?:^|\s)(?P<qual>(?:static\s+|const\s+|unsigned\s+|signed\s+|extern\s+|ZLIB_INTERNAL\s+)*)"
    r"(?P<ctype>[A-Za-z_]\w*(?:\s*\*)?)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*"
    r"(?P<dims>(?:\[[^\]]*\])*)\s*"
    r"=\s*\{",
    re.MULTILINE,
)


# Map GENUINE C-LANGUAGE PRIMITIVES to Rust. These are the C standard and
# stdint.h — universal across every codebase, NOT codebase-specific. Any
# codebase-specific alias (zlib's `Bytef`, Lua's `lu_byte`, PX4's `hrt_abstime`)
# is resolved dynamically from the subject's own `typedef` / type-macro
# declarations via `build_typedef_map()` — never hardcoded. This keeps the
# harness general: the model's translation transfers to unseen code because
# type resolution reads the code, it doesn't look names up in a curated table.
_C_TYPE_TO_RUST: dict[str, str] = {
    "char": "u8",
    "unsigned char": "u8",
    "signed char": "i8",
    "short": "i16",
    "short int": "i16",
    "unsigned short": "u16",
    "unsigned short int": "u16",
    "signed short": "i16",
    "int": "i32",
    "unsigned": "u32",
    "unsigned int": "u32",
    "signed int": "i32",
    "long": "i64",
    "long int": "i64",
    "unsigned long": "u64",
    "unsigned long int": "u64",
    "signed long": "i64",
    "long long": "i64",
    "long long int": "i64",
    "unsigned long long": "u64",
    "unsigned long long int": "u64",
    "float": "f32",
    "double": "f64",
    "long double": "f64",
    "_Bool": "bool",
    "size_t": "usize",
    "ssize_t": "isize",
    "ptrdiff_t": "isize",
    "uintptr_t": "usize",
    "intptr_t": "isize",
    "uint8_t": "u8",
    "uint16_t": "u16",
    "uint32_t": "u32",
    "uint64_t": "u64",
    "int8_t": "i8",
    "int16_t": "i16",
    "int32_t": "i32",
    "int64_t": "i64",
    "uint_fast8_t": "u8",
    "uint_fast16_t": "u32",
    "uint_fast32_t": "u32",
    "uint_fast64_t": "u64",
    "uint_least8_t": "u8",
    "uint_least16_t": "u16",
    "uint_least32_t": "u32",
    "uint_least64_t": "u64",
    "intmax_t": "i64",
    "uintmax_t": "u64",
}

# A typedef base made only of these keywords is a scalar we can resolve to a
# Rust primitive. Anything else (struct/union/enum/function-pointer/array/
# pointer aggregate) is deliberately NOT resolved as a scalar alias.
_SCALAR_KEYWORDS = frozenset({
    "unsigned", "signed", "long", "short", "int", "char",
    "double", "float", "void", "_Bool",
})

# `typedef <base> <alias>;` where base is a plain (possibly multi-word) type
# name and alias is a single identifier. Excludes struct/union/enum/pointer/
# array/function-pointer forms because the char class stops at `*({[`.
_TYPEDEF_RE = re.compile(
    r"\btypedef\s+([A-Za-z_][\w ]*?)\s+([A-Za-z_]\w*)\s*;",
    re.MULTILINE,
)
# `#define ALIAS <scalar-type-keywords>` — some libraries alias scalar types
# with a macro instead of a typedef (Lua's `#define LUAI_UACINT long long`).
_TYPE_MACRO_RE = re.compile(
    r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+"
    r"((?:unsigned|signed|long|short|int|char|double|float|void|_Bool)"
    r"(?:\s+(?:unsigned|signed|long|short|int|char|double|float))*)\s*$",
    re.MULTILINE,
)


def build_typedef_map(texts) -> dict[str, str]:
    """Read a subject's own `typedef` and scalar type-macro declarations from
    its source/header texts and return an {alias -> base-type} map.

    This is what makes type resolution GENERAL: instead of a hardcoded table of
    one library's type names, the harness learns each codebase's aliases from
    the codebase itself. `typedef unsigned char lu_byte;` teaches `lu_byte`;
    `typedef LUAI_UACINT lua_Integer;` chains through the macro map.

    `texts` is any iterable of C source/header strings (the subject's `.c`+`.h`).
    """
    tmap: dict[str, str] = {}
    for text in texts:
        if not text:
            continue
        for m in _TYPEDEF_RE.finditer(text):
            base = re.sub(r"\s+", " ", m.group(1).strip())
            alias = m.group(2).strip()
            # Skip aggregate bases — only scalar aliases resolve to primitives.
            if any(k in base.split() for k in ("struct", "union", "enum")):
                continue
            if alias and alias != base:
                tmap.setdefault(alias, base)
        for m in _TYPE_MACRO_RE.finditer(text):
            alias = m.group(1).strip()
            base = re.sub(r"\s+", " ", m.group(2).strip())
            if alias and alias != base:
                tmap.setdefault(alias, base)
    return tmap


def resolve_scalar_alias(c_type: str, typedef_map: dict[str, str]) -> str:
    """If `c_type` is a BARE (non-pointer) scalar typedef alias, resolve it to its
    base C primitive via the subject's typedefs; otherwise return it unchanged.

    Lets shape classifiers that match on primitive C type names recognize a
    library's aliased scalars — `lua_Integer`/`lua_Unsigned`/`Instruction`/`uInt`
    -> `long long`/`unsigned int`/... — read from the subject's OWN typedefs, not
    a hardcoded table. Pointer and struct/aggregate types are left intact (their
    shapes are handled by the pointer-shape classifiers, and structs must stay
    named). Multi-word primitives (`unsigned int`) pass through untouched."""
    if not typedef_map or "*" in c_type:
        return c_type
    core = re.sub(r"\b(?:const|volatile)\b", "", c_type).strip()
    core = re.sub(r"\s+", " ", core)
    if not core or core in _C_TYPE_TO_RUST:
        return c_type
    resolved = _resolve_typedef_chain(core, typedef_map)
    if resolved != core and resolved in _C_TYPE_TO_RUST:
        return resolved
    return c_type


def _resolve_typedef_chain(c: str, typedef_map: dict[str, str]) -> str:
    """Walk alias -> base through the subject's typedef map until a C primitive
    (or a name the map doesn't know). Cycle- and depth-guarded."""
    seen: set[str] = set()
    depth = 0
    while (
        c not in _C_TYPE_TO_RUST
        and c in typedef_map
        and c not in seen
        and depth < 32
    ):
        seen.add(c)
        c = re.sub(r"\s+", " ", typedef_map[c].replace("*", "").strip())
        depth += 1
    return c


def _rust_type_for(c_type: str, typedef_map: dict[str, str] | None = None) -> str:
    """Best-effort translation of a C type name to Rust.

    Resolution order: normalize -> walk the subject's own typedef chain to a
    base type -> map that primitive to Rust. `typedef_map` comes from
    `build_typedef_map()` over the subject's sources; when absent we still map
    genuine C primitives.
    """
    c = c_type.strip()
    # Collapse whitespace
    c = re.sub(r"\s+", " ", c)
    # Drop pointer-asterisks — we don't emit pointer consts
    c = c.replace("*", "").strip()
    # Strip cv-qualifiers that don't affect the representation.
    c = re.sub(r"\b(?:const|volatile)\b", "", c).strip()
    c = re.sub(r"\s+", " ", c)
    # Resolve the subject's own aliases (Bytef, lu_byte, hrt_abstime, ...).
    if typedef_map:
        c = _resolve_typedef_chain(c, typedef_map)
    if c in _C_TYPE_TO_RUST:
        return _C_TYPE_TO_RUST[c]
    # Sometimes C uses `unsigned long int` — try normalized joins.
    parts = c.split()
    if len(parts) >= 2:
        joined = " ".join(parts)
        if joined in _C_TYPE_TO_RUST:
            return _C_TYPE_TO_RUST[joined]
        # Try without a leading qualifier keyword.
        if parts[0] in ("const", "unsigned", "signed"):
            rest = " ".join(parts[1:])
            if rest in _C_TYPE_TO_RUST:
                return _C_TYPE_TO_RUST[rest]
    # Fallback: pass through (may be a struct type the caller knows about).
    return c or "u32"


# ---------------------------------------------------------------------------
# Expression translation: C literal → Rust literal
# ---------------------------------------------------------------------------

_C_NUM_LITERAL_RE = re.compile(
    r"""^
    (?P<sign>-)?
    (?:
      0[xX](?P<hex>[0-9a-fA-F]+)
      |
      0[bB](?P<bin>[01]+)
      |
      0(?P<oct>[0-7]+)
      |
      (?P<dec>\d+)
    )
    # Optional trailing suffix: stdint-style ('u32', 'i64', 'usize') takes
    # priority over plain C99 ('u', 'U', 'l', 'L', 'UL', 'ULL', etc.), so
    # we match the width-bearing form first. Both are stripped — the Rust
    # emitter applies a type suffix appropriate to the declared const type.
    (?P<suffix>
        [uUiI](?:8|16|32|64|128|size)
        |
        (?:[uU][lL]{0,2}|[lL]{1,2}[uU]?)
    )?
    $
    """,
    re.VERBOSE,
)


def _c_literal_to_rust(expr: str, rust_type: str) -> str | None:
    """Convert a single C literal or simple expression to a Rust expression.

    Returns None if the expression is too complex to translate safely (the
    extractor will fall back to emitting the raw C text as a comment).
    """
    s = expr.strip().rstrip(";").strip()
    if not s:
        return None
    # Strip parens wrapping the whole thing
    while s.startswith("(") and s.endswith(")"):
        inner = s[1:-1].strip()
        # Avoid stripping if the parens are unbalanced (e.g., "(1<<2) | (3<<4)")
        if _parens_balanced(inner):
            s = inner
        else:
            break
    # Integer literal
    m = _C_NUM_LITERAL_RE.match(s)
    if m:
        sign = m.group("sign") or ""
        if m.group("hex"):
            return f"{sign}0x{m.group('hex').lower()}"
        if m.group("bin"):
            return f"{sign}0b{m.group('bin')}"
        if m.group("oct") is not None:
            return f"{sign}0o{m.group('oct') or '0'}"
        return f"{sign}{m.group('dec')}"
    # Char literal
    if len(s) >= 3 and s[0] == "'" and s[-1] == "'":
        ch = s[1:-1]
        # Single char or escape
        if ch == "\\n":
            return "b'\\n' as u32"
        if ch == "\\t":
            return "b'\\t' as u32"
        if ch == "\\0":
            return "0"
        if len(ch) == 1:
            return f"{ord(ch)}"
    # String literal — emit as a byte string (safer than &str for C-origin)
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return f"b{s}"
    # Simple expression: arithmetic/bitwise on numeric literals.
    # Only accept if every token is safe.
    if _is_safe_const_expr(s):
        return _translate_safe_expr(s, rust_type)
    return None


def _parens_balanced(s: str) -> bool:
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


_SAFE_TOKEN_RE = re.compile(
    r"""
    \s+ |                                     # whitespace
    (?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+)[uUlL]* |   # numeric literals with suffix
    '[^']'                           |        # char literal
    [A-Za-z_]\w*                     |        # identifier (other constants)
    [()+\-*/<>|&^~%]                 |        # operator chars (single)
    <<                                |       # left shift
    >>                                        # right shift
    """,
    re.VERBOSE,
)


def _is_safe_const_expr(s: str) -> bool:
    """True if s tokenizes as a safe subset of C const expressions.

    Rejects function-call patterns (identifier immediately followed by `(`)
    since these cannot be const-evaluated by the extractor. Without this
    check, `foo(42)` would tokenize as `foo`, `(`, `42`, `)` — all safe
    individually — and get emitted as a Rust const, producing bad code.
    """
    tokens: list[str] = []
    pos = 0
    while pos < len(s):
        m = _SAFE_TOKEN_RE.match(s, pos)
        if not m or m.end() == pos:
            return False
        tok = m.group(0)
        if not tok.isspace():
            tokens.append(tok)
        pos = m.end()
    # Reject IDENT '(' patterns — that's a function call, not a const.
    # (Parenthesized sub-expressions like `(1 << 2)` start with `(` token,
    # not with an identifier, so this only catches the call case.)
    ident_re = re.compile(r"^[A-Za-z_]\w*$")
    for i in range(len(tokens) - 1):
        if ident_re.match(tokens[i]) and tokens[i + 1] == "(":
            return False
    return True


def _translate_safe_expr(s: str, rust_type: str) -> str:
    """Translate a safe C const expression to Rust. Numeric literals gain
    rust_type-appropriate suffixes if the result is unambiguous."""
    # Strip any U/L suffixes from numeric literals; Rust uses explicit type
    # annotations on the enclosing const, not suffixes.
    s = re.sub(r"(\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|\d+))[uUlL]+\b", r"\1", s)
    # Handle char literals
    s = re.sub(r"'(\\.|[^\\])'", lambda m: str(ord(_unescape_c_char(m.group(1)))), s)
    return s.strip()


def _unescape_c_char(s: str) -> str:
    if not s.startswith("\\"):
        return s
    return {
        "\\n": "\n", "\\t": "\t", "\\r": "\r", "\\0": "\0",
        "\\\\": "\\", "\\'": "'", '\\"': '"',
    }.get(s, s[-1])


# ---------------------------------------------------------------------------
# Primary API
# ---------------------------------------------------------------------------

@dataclass
class ExtractionReport:
    extracted: list[ConstantSpec]
    skipped: list[tuple[str, str]]  # (name, reason)

    @property
    def count(self) -> int:
        return len(self.extracted)


_RUST_RESERVED = {
    # Rust keywords that must never appear as a const value expression
    "as", "break", "const", "continue", "crate", "else", "enum", "extern",
    "false", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod",
    "move", "mut", "pub", "ref", "return", "self", "Self", "static", "struct",
    "super", "trait", "true", "type", "unsafe", "use", "where", "while",
    "async", "await", "dyn", "abstract", "become", "box", "do", "final",
    "macro", "override", "priv", "typeof", "unsized", "virtual", "yield",
}


def _is_c_preprocessor_marker(value: str) -> bool:
    """True if the value is a C construct that Rust can't represent as a const.

    Examples from zlib trees.c:
      #define TCONST           (empty body — visibility qualifier marker)
      #define TCONST const     (keyword-value — C qualifier)
      #define FAR              (calling-convention marker)
    These aren't real constants; they're token-pasting helpers.
    """
    v = value.strip()
    if not v:
        return True
    # A single Rust keyword used as a value expression — invalid
    if v in _RUST_RESERVED:
        return True
    # A sequence of only reserved words (e.g., "const volatile") or C
    # storage-class / qualifier / calling-convention keywords used as macro
    # bodies (`#define FORCE_INLINE inline`, `#define REG register`). These are
    # qualifiers, not values — emitting `pub const X = inline` is E0423. This is
    # universal across C codebases (murmur3's FORCE_INLINE, many others).
    parts = v.split()
    if all(p in _RUST_RESERVED or p in _C_QUALIFIER_MARKERS for p in parts):
        return True
    return False


# C storage-class specifiers, type qualifiers, and calling-convention markers
# that appear as macro bodies but are NOT constant values.
_C_QUALIFIER_MARKERS = frozenset({
    "volatile", "inline", "register", "restrict", "auto", "extern", "static",
    "__inline", "__inline__", "__forceinline", "__restrict", "__restrict__",
    "__volatile__", "_Noreturn", "__attribute__", "__cdecl", "__stdcall",
    "__fastcall", "__far", "__near", "FAR", "NEAR", "__declspec",
})


def extract_constants(
    c_source: str,
    c_file: str = "",
    typedef_map: dict[str, str] | None = None,
) -> ExtractionReport:
    """Extract all constants from a C translation unit.

    Does NOT run the C preprocessor — works on the raw source. This means
    conditional compilation blocks inside `#if 0` etc. are still visible
    (acceptable: they'd be dead Rust consts but don't break anything).

    `typedef_map` (from `build_typedef_map()` over the whole subject) lets
    carried-table element types resolve through the subject's own aliases.
    Typedefs declared in THIS unit are always folded in as a baseline, so a
    self-contained single file still resolves its own aliases with no caller
    help.
    """
    extracted: list[ConstantSpec] = []
    skipped: list[tuple[str, str]] = []

    # Always self-scan this unit's typedefs; merge any caller-supplied
    # cross-file map on top (caller map wins on conflict).
    local_types = build_typedef_map([c_source])
    if typedef_map:
        local_types.update(typedef_map)
    typedef_map = local_types

    # Already-seen names (later definitions win, matching C semantics).
    seen: dict[str, int] = {}

    # 1. #define — skip function-like
    for m in _DEFINE_RE.finditer(c_source):
        full = m.group(0)
        name = m.group(1)
        value = (m.group(2) or "").strip()
        if not value:
            continue
        # Skip if the NAME collides with a Rust reserved word. Rust would
        # require r#<name> raw-identifier syntax, but consts in pub-use
        # chains can't be raw — skip rather than risk compile breakage.
        if name in _RUST_RESERVED:
            skipped.append((name, f"rust reserved name"))
            continue
        # Skip function-like macros — `#define FOO(x) ...`
        # (the value group starts with `(` after the name word but _DEFINE_RE
        # only matches when name is followed by whitespace, not `(`).
        # Extra guard: if the line-matched substring has `(` immediately
        # after the name, it's a function-like macro and _DEFINE_RE would
        # have missed it. Still, defend against edge cases.
        define_line = c_source[m.start():m.end()]
        if re.match(rf"\s*#\s*define\s+{re.escape(name)}\s*\(", define_line):
            continue
        # Strip trailing line comments
        value = re.sub(r"/\*.*?\*/", "", value, flags=re.DOTALL).strip()
        value = re.sub(r"//.*$", "", value).strip()
        if not value:
            continue
        # Skip C preprocessor markers (TCONST, FAR, calling conventions, etc.)
        # that don't translate to Rust constants.
        if _is_c_preprocessor_marker(value):
            skipped.append((name, f"c preprocessor marker: {value!r}"))
            continue
        # Skip scalar TYPE-alias macros (`#define LUAI_UACINT long long`) — the
        # value is a type, not a constant. build_typedef_map() already absorbed
        # it for type resolution; emitting it as `pub const = long long` is bad
        # Rust. A value made only of C scalar-type keywords is a type alias.
        if all(tok in _SCALAR_KEYWORDS for tok in value.split()):
            skipped.append((name, f"type-alias macro: {value!r}"))
            continue
        rust_type = _infer_type_from_literal(value)
        rust_expr = _c_literal_to_rust(value, rust_type)
        if rust_expr is None:
            skipped.append((name, f"complex expression: {value[:60]!r}"))
            continue
        line_no = c_source.count("\n", 0, m.start()) + 1
        extracted.append(ConstantSpec(
            name=name,
            rust_type=rust_type,
            rust_expr=rust_expr,
            c_origin=full.strip()[:200],
            c_file=c_file,
            c_line=line_no,
        ))
        seen[name] = line_no

    # 2. enum { ... }
    for m in _ENUM_BLOCK_RE.finditer(c_source):
        body = m.group(1)
        next_value = 0
        for member in body.split(","):
            member = member.strip()
            if not member:
                continue
            # Member: NAME or NAME = EXPR
            if "=" in member:
                nm, expr = member.split("=", 1)
                nm = nm.strip()
                expr = expr.strip()
                rust_expr = _c_literal_to_rust(expr, "i32") or expr
                # Try numeric parse for auto-increment continuation
                try:
                    next_value = int(rust_expr, 0) + 1
                except ValueError:
                    next_value = 0  # reset
            else:
                nm = member
                rust_expr = str(next_value)
                next_value += 1
            if not nm.isidentifier():
                continue
            line_no = c_source.count("\n", 0, m.start()) + 1
            extracted.append(ConstantSpec(
                name=nm,
                rust_type="i32",
                rust_expr=rust_expr,
                c_origin=f"enum member {nm}",
                c_file=c_file,
                c_line=line_no,
            ))

    # 3. static const TYPE NAME[N] = { ... }
    for spec in _extract_static_const_tables(c_source, c_file, typedef_map):
        extracted.append(spec)

    # Post-pass: drop a const whose value is a bare identifier that references a
    # symbol we never defined. A `#define X Y` with Y a lone identifier is only
    # sound if Y is another extracted const/enum; when it isn't, Y is a DANGLING
    # reference and `pub const X = Y` is E0425 that breaks the whole crate. This
    # is how libraries plant POISON macros (parson: `#define sscanf
    # THINK_TWICE_ABOUT_USING_SSCANF`, `#define strcpy USE_MEMCPY_INSTEAD_OF_STRCPY`)
    # to forbid a call at compile time — never real constants.
    _defined = {c.name for c in extracted}
    _ident = re.compile(r"^[A-Za-z_]\w*$")
    _kept, _dangling = [], []
    for c in extracted:
        expr = (c.rust_expr or "").strip()
        if _ident.match(expr) and expr not in _defined and expr not in ("true", "false"):
            _dangling.append(c)
            skipped.append((c.name, f"dangling identifier reference: {expr!r}"))
        else:
            _kept.append(c)
    extracted = _kept

    return ExtractionReport(extracted=extracted, skipped=skipped)


def _infer_type_from_literal(value: str) -> str:
    """Pick a sensible Rust type based on the literal's shape."""
    v = value.strip()
    m = _C_NUM_LITERAL_RE.match(v)
    if m:
        # Suffix signals
        suffix = (m.group("suffix") or "").lower()
        if "ull" in suffix or "ul" in suffix or "l" in suffix:
            return "u64" if "u" in suffix else "i64"
        if "u" in suffix:
            return "u32"
        # Hex with > 32 bits → u64
        if m.group("hex") and len(m.group("hex")) > 8:
            return "u64"
        return "u32" if v.lstrip("-").startswith(("0x", "0b", "0X", "0B")) else "i32"
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return "&'static [u8]"
    return "u32"


def _extract_static_const_tables(
    c_source: str,
    c_file: str,
    typedef_map: dict[str, str] | None = None,
) -> list[ConstantSpec]:
    """Find `static const TYPE NAME[DIM] = { ... };` and extract."""
    out: list[ConstantSpec] = []
    for m in _STATIC_CONST_RE.finditer(c_source):
        qual = (m.group("qual") or "").strip()
        if "static" not in qual and "const" not in qual:
            continue
        ctype = (m.group("ctype") or "").strip()
        # Fold relevant width-qualifiers (unsigned/signed) back into the
        # type string so `_rust_type_for` sees `"unsigned int"` not `"int"`.
        # Without this, `static const unsigned int table[]` renders as
        # `[i32; N]` instead of `[u32; N]`.
        qual_parts = [
            p for p in qual.split()
            if p in ("unsigned", "signed")
        ]
        if qual_parts:
            ctype = (" ".join(qual_parts) + " " + ctype).strip()
        name = m.group("name")
        dims = m.group("dims") or ""
        # Walk braces to find the end
        open_brace = m.end() - 1  # _STATIC_CONST_RE ends with `{`
        close = _find_matching_brace(c_source, open_brace)
        if close < 0:
            continue
        body = c_source[open_brace + 1:close]
        # Count elements to verify declared dimension if present
        elements = _split_top_level_commas(body)
        # Build Rust array
        rust_elems: list[str] = []
        skip = False
        for e in elements:
            e = e.strip()
            if not e:
                continue
            rust_expr = _c_literal_to_rust(e, _rust_type_for(ctype, typedef_map))
            if rust_expr is None:
                skip = True
                break
            rust_elems.append(rust_expr)
        if skip or not rust_elems:
            continue
        # Rust type: [T; N]
        elem_rust = _rust_type_for(ctype, typedef_map)
        n = len(rust_elems)
        rust_type = f"[{elem_rust}; {n}]"
        rust_expr = "[" + ", ".join(rust_elems) + "]"
        line_no = c_source.count("\n", 0, m.start()) + 1
        out.append(ConstantSpec(
            name=name,
            rust_type=rust_type,
            rust_expr=rust_expr,
            c_origin=f"static const {ctype} {name}{dims}",
            c_file=c_file,
            c_line=line_no,
        ))
    return out


def _find_matching_brace(text: str, open_pos: int) -> int:
    """Find matching `}` — reuses the scrubber helper for consistency."""
    from alchemist.implementer.scrubber import find_matching_brace
    return find_matching_brace(text, open_pos)


def _split_top_level_commas(s: str) -> list[str]:
    """Split on commas that are NOT inside nested braces, parens, or strings."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "*":
            end = s.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        if ch == "/" and nxt == "/":
            nl = s.find("\n", i + 2)
            i = n if nl == -1 else nl + 1
            continue
        if ch == '"':
            end = i + 1
            while end < n and s[end] != '"':
                if s[end] == "\\":
                    end += 2
                else:
                    end += 1
            buf.append(s[i:end + 1])
            i = end + 1
            continue
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    if buf:
        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
    return parts


# ---------------------------------------------------------------------------
# Emission: ConstantSpec → Rust source
# ---------------------------------------------------------------------------

def render_constants_block(consts: list[ConstantSpec]) -> str:
    """Render a list of constants as a Rust `pub const` block.

    Conflict resolution: Rust forbids `pub const NAME` to appear twice
    in the same scope. C allows `#define NAME` to appear in multiple
    `#ifdef` branches — the preprocessor resolves to one. Without
    running the preprocessor, we see all branches. Rule: LATER wins
    (matches naive "last #define takes effect" intuition, which works
    for Z_TESTN-style testing hooks that override a default).

    Ordering: preserve extraction order (which follows C source order);
    for duplicates, keep ONLY the last occurrence so the emitted Rust
    always compiles.
    """
    # Dedupe by name, keeping last
    seen: dict[str, int] = {}
    for i, c in enumerate(consts):
        seen[c.name] = i
    unique = [consts[i] for i in sorted(seen.values())]
    lines: list[str] = []
    for c in unique:
        if c.c_origin:
            lines.append(f"/// {c.c_origin}")
        # Carried C constants keep their C names (log_2, NMAX, ...), which
        # violate Rust's UPPER_CASE / non-snake conventions. Under the verify
        # gate's `-D warnings` that lint is a hard error -> compile-fail-revert
        # -> stub. Allow it per-const so a table like `log_2` compiles.
        lines.append("#[allow(non_upper_case_globals, non_snake_case)]")
        lines.append(f"pub const {c.name}: {c.rust_type} = {c.rust_expr};")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def extract_from_path(
    path: Path,
    typedef_map: dict[str, str] | None = None,
) -> ExtractionReport:
    """Convenience: extract from a single C file. Pass a `typedef_map` built
    over the whole subject (via `build_typedef_map`) so cross-header aliases
    resolve; otherwise only this file's own typedefs are seen."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return extract_constants(text, c_file=str(path), typedef_map=typedef_map)
