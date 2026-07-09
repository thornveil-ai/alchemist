"""Reference probe — per-function C-to-Rust transliteration.

For any AlgorithmSpec the pipeline is about to generate, the probe:
  1. Locates the function's C source body via source_files + function name
  2. Asks the LLM for a direct, safe-Rust transliteration (no idiom rewrites,
     no optimization — just mechanical translation preserving structure)
  3. Compile-checks the candidate against a shared types shim
  4. If it compiles, returns it as a reference implementation the TDD loop
     can inject into its prompt

This is the generalization primitive: hand-curated reference impls cover
common primitives (Adler-32, CRC-32) but the long tail of zlib/mbedTLS
functions needs auto-generated references to avoid hand-writing one per
function. The probe IS that auto-generation.

Key differences from regular Stage 4 generation:
  - Probe aims for 1:1 structural correspondence with the C body
  - Probe output is not shipped; it's a template the regular LLM adapts
  - Probe is permitted to produce non-idiomatic Rust — correctness first
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from alchemist.extractor.schemas import AlgorithmSpec
from alchemist.llm.client import AlchemistLLM, LLMResponse
from alchemist.references.registry import ReferenceImpl


_PROBE_SYSTEM = """You produce literal transliterations of C into safe Rust.
No optimization. No idiom rewrite. One Rust statement per C statement where
possible. Preserve variable names, loop structure, and branch shape exactly.
Use safe Rust only: NO `unsafe` blocks, NO raw pointers.

## C type mapping

C types must be converted to their Rust equivalents. NEVER keep a C typedef
in the Rust output. Common mappings:

  - `unsigned char`, `Bytef`, `uchf`, `Byte`      → u8
  - `short`, `ushf`                               → i16 / u16
  - `int`, `uInt`                                 → i32 / u32
  - `unsigned int`, `uLong`                       → u32 / u64
  - `size_t`, `z_size_t`, `ptrdiff_t`             → usize / isize
  - `long long`, `int64_t`                        → i64
  - `z_off_t`, `off_t`                            → i64
  - `void *`, `voidpf`                            → do not translate raw;
    express with `&[u8]` / `&mut [u8]` / explicit owned types

## Pointer conversions

  - `const unsigned char *buf, size_t len` → `buf: &[u8]` (length from .len())
  - `unsigned char *out, size_t len`       → `out: &mut [u8]`
  - `size_t *len_in_out`                   → `len: &mut usize`
  - `const char *s` where nul-terminated   → `s: &str`
  - `z_streamp strm` / `z_stream *strm`    → `strm: &mut DeflateStream`
                                             (or InflateStream as appropriate)

## Struct access

When the C body references struct fields via `strm->state->X`, translate
to `strm.state.X` (Rust flattens pointer deref). When zlib uses the
`state` subfield of a stream (e.g., `s = strm->state`), translate to
`let s = &mut strm.state;` and then use `s.X` through the body.

## Memory primitives

  - `memcpy(dst, src, n)` → `dst[..n].copy_from_slice(&src[..n])`
  - `memset(buf, 0, n)`   → `for b in &mut buf[..n] { *b = 0; }`
  - `memmove(dst, src, n)` (overlapping) → `dst.copy_within(..n, dst_start)`

## Control flow

  - `goto label;` over a forward-only structured region → use a `break 'label`
    out of a labeled loop, OR restructure to a single if/else chain. Never
    use a raw jump-equivalent.
  - Early `return VALUE;` → `return VALUE;` (Rust allows it)

## Mutability

Rust parameters are immutable by default. Before writing the body, audit
EVERY parameter: if the C body reassigns it, mutates it, or advances a
pointer through it, shadow it with a `let mut` binding as the FIRST
statement of the function body.

When in doubt, shadow. Over-shadowing is harmless (unused_mut warnings).
Under-shadowing is a compile error.

    // C has: `adler -= BASE; buf += 16; len -= 16;`
    pub fn f(adler: u32, buf: &[u8], len: usize) -> u32 {
        let mut adler = adler;   // REQUIRED: C reassigns it
        let mut buf = buf;       // REQUIRED: C advances the pointer
        let mut len = len;       // REQUIRED: C decrements it
        // ... rest of body can freely use `adler -= 65521; buf = &buf[16..]; len -= 16;`
    }

Walk through the C source once looking for `x = y`, `x += y`, `x++`, `x--`,
`++x`, `--x`, `x = foo(x)` — every such variable MUST be shadowed if it's
a parameter. This applies even to pointer-like parameters: `buf = &buf[16..]`
requires `let mut buf = buf;` above it.

## Return type discipline

The signature's return type is LAW. Every `return` expression MUST match it.
If your intermediate variables are a wider type (e.g., u64 for overflow
safety but the return type is u32), cast explicitly: `return result as u32;`
not `return result;` hoping for implicit conversion.

## Numeric literals and types

Use typed suffixes on numeric literals when mixing types: `65521u32`, not
bare `65521`. Inside arithmetic with u64 variables, use `u64` literals.
When the C code uses `unsigned long` constants that fit in u32, prefer
u32 unless the algorithm requires wider intermediate values.

Return ONLY the Rust function definition — signature + body — no explanation,
no markdown, no additional text.
"""


_PROBE_PROMPT = """Translate this C function into safe Rust.

C source:
```c
{c_body}
```

Required Rust signature (match exactly):
```rust
{signature}
```

Relevant shared types already in scope (fields you may reference):
{struct_context}

Previous failure to correct (if any):
{previous_failure}

Return the complete Rust function — signature line + body — with no other text.
"""


@dataclass
class ProbeResult:
    """Result of probing a C function for its Rust transliteration."""
    algorithm: str
    success: bool
    rust_source: str = ""
    error: str = ""
    notes: str = ""


_ARRAY_DEF_RE = re.compile(
    r"(?:^|\n)[ \t]*(?:static\s+)?(?:const\s+)?[A-Za-z_]\w*\s+([A-Za-z_]\w*)\s*"
    r"\[[^\]]*\]\s*=\s*\{"
)


def _read_with_includes(source_path: Path, *, include_dirs=None, depth: int = 2) -> str:
    """Read a C file plus its local `#include "..."` files (generated *.inc tables, shared
    headers), bounded recursion. Resolves each include relative to the includer AND against
    `include_dirs` (the -I search path, so a bare `#include "checksum.h"` that lives in
    include/ is found) — a table or #define in a separate file is then visible to the scanners."""
    try:
        text = source_path.read_text(errors="replace")
    except OSError:
        return ""
    if depth <= 0:
        return text
    parts = [text]
    _dirs = [Path(d) for d in (include_dirs or [])]
    for m in re.finditer(r'#\s*include\s*"([^"]+)"', text):
        inc_name = m.group(1)
        cands = [source_path.parent / inc_name]
        for d in _dirs:
            cands.append(d / inc_name)
            cands.append(d / Path(inc_name).name)
        for cand in cands:
            try:
                cand = cand.resolve()
                if cand.exists() and cand.is_file():
                    parts.append(_read_with_includes(
                        cand, include_dirs=include_dirs, depth=depth - 1))
                    break
            except OSError:
                continue
    return "\n".join(parts)


def extract_referenced_arrays(source_path: Path, fn_body: str,
                              *, include_dirs=None, max_chars: int = 40000) -> list[str]:
    """Return file-level const-array (lookup-table) DEFINITIONS whose name is referenced in
    `fn_body`. Feeding these into the fill prompt lets the model reproduce a table EXACTLY
    instead of guessing hundreds of magic numbers — the #1 cause of compile-but-diverge on
    table-driven code (CRC/hash lookup tables). Uses brace-matching, no tree-sitter needed."""
    text = _read_with_includes(source_path, include_dirs=include_dirs)
    if not text:
        return []
    out: list[str] = []
    for m in _ARRAY_DEF_RE.finditer(text):
        name = m.group(1)
        if re.search(r"\b" + re.escape(name) + r"\b", fn_body) is None:
            continue
        brace = text.index("{", m.start())
        depth, j = 0, brace
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        semi = text.find(";", j)
        end = semi + 1 if semi != -1 else j + 1
        snippet = text[m.start():end].strip()
        if 0 < len(snippet) <= max_chars:
            out.append(snippet)
    return out


_C_ARR_TY = {
    "uint8_t": "u8", "uint16_t": "u16", "uint32_t": "u32", "uint64_t": "u64",
    "int8_t": "i8", "int16_t": "i16", "int32_t": "i32", "int64_t": "i64",
    "unsigned char": "u8", "unsigned short": "u16", "unsigned int": "u32",
    "unsigned long": "u64", "unsigned": "u32", "char": "u8", "int": "i32",
    "long": "i64", "short": "i16",
}
_C_ARR_HEAD = re.compile(
    r"^\s*(?:static\s+)?(?:const\s+)?"
    r"(unsigned char|unsigned short|unsigned int|unsigned long|unsigned|"
    r"uint8_t|uint16_t|uint32_t|uint64_t|int8_t|int16_t|int32_t|int64_t|"
    r"char|short|int|long)\s+([A-Za-z_]\w*)\s*\[[^\]]*\]\s*=\s*\{(.*)\}\s*;\s*$",
    re.DOTALL,
)


def c_array_to_rust_const(c_def: str) -> tuple[str, str] | None:
    """Convert a C file-level const-array definition to a Rust `pub const NAME: [T; N] = [...]`.
    Returns (name, rust_const) or None if the type isn't a plain integer array. This lets a
    lookup table be EMITTED into the crate so the model references it by name rather than
    (unreliably) re-typing hundreds of values."""
    m = _C_ARR_HEAD.match(c_def.strip())
    if not m:
        return None
    ctype, name, body = m.group(1).strip(), m.group(2), m.group(3)
    rust_ty = _C_ARR_TY.get(ctype)
    if rust_ty is None:
        return None
    vals = []
    for tok in body.split(","):
        tok = tok.strip()
        if not tok:
            continue
        tok = re.sub(r"[uUlL]+$", "", tok)          # strip 0x..UL suffixes
        if not re.fullmatch(r"[-+]?(?:0[xX][0-9a-fA-F]+|\d+)", tok):
            return None                              # not a plain integer literal
        vals.append(tok)
    if not vals:
        return None
    rust = f"pub const {name}: [{rust_ty}; {len(vals)}] = [{', '.join(vals)}];"
    return name, rust


# Two-group form: NAME + VALUE. Named _DEFINE_KV_RE to avoid colliding with the
# name-only _DEFINE_RE defined later in this module (extract_referenced_macros).
_DEFINE_KV_RE = re.compile(
    r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+(\S.*)$",
    re.MULTILINE)


def _strip_c_comment(val: str) -> str:
    """Drop a trailing // or /* ... */ comment from a captured #define value."""
    val = re.sub(r"/\*.*?\*/", "", val)
    val = re.sub(r"//.*$", "", val)
    return val.strip()


def extract_referenced_defines(source_path: Path, fn_body: str, *, include_dirs=None) -> list[str]:
    """Return object-like `#define NAME VALUE` macros whose NAME is referenced in `fn_body`
    (with the .c's local #includes resolved, so defines in a shared header are found). Feeding
    these lets the model use the EXACT constant — a CRC start value, polynomial or magic number
    — instead of guessing it (e.g. CRC_START_64_WE = 0xFFFFFFFFFFFFFFFF, which the model
    otherwise wrote as 0x0, failing a correct crc_64_we)."""
    text = _read_with_includes(source_path, include_dirs=include_dirs)
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _DEFINE_KV_RE.finditer(text):
        name = m.group(1)
        val = _strip_c_comment(m.group(2))
        if name in seen or not val:
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", fn_body):
            seen.add(name)
            out.append(f"#define {name} {val}")
    return out


def extract_c_function_body(source_path: Path, function_name: str) -> str | None:
    """Locate a C function by name in the given source file and return its full text.

    Uses tree-sitter to parse and find the matching definition. Returns the
    complete function-definition text (signature + body) as a str, or None
    if the function isn't found.
    """
    if not source_path.exists():
        return None
    try:
        import tree_sitter_c as tsc
        from tree_sitter import Language, Parser
    except ImportError:
        # No tree-sitter in this environment — the brace-matcher is pure Python
        # and handles the common cases, so fall back to it instead of giving up
        # (returning None here made the model translate with NO reference C).
        try:
            text = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return _extract_by_brace_match(text, function_name)

    source = source_path.read_bytes()
    language = Language(tsc.language())
    parser = Parser(language)
    tree = parser.parse(source)

    def walk(node):
        if node.type == "function_definition":
            # Find the declarator's inner identifier
            declarator = node.child_by_field_name("declarator")
            if declarator is not None:
                name_node = _find_identifier(declarator)
                if name_node is not None:
                    name = source[name_node.start_byte:name_node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if name == function_name:
                        return source[node.start_byte:node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
        for child in node.children:
            result = walk(child)
            if result is not None:
                return result
        return None

    result = walk(tree.root_node)
    # Fall back not just when tree-sitter returns None, but also when it returns
    # an EMPTY/whitespace body — which is what happens on API-macro'd signatures
    # (e.g. jsmn's `JSMN_API int jsmn_parse(...)`, whose unknown `JSMN_API` token
    # makes tree-sitter match a zero-width definition). A brace-matching text scan
    # recovers these and the huge macro-heavy zlib functions alike.
    # See docs/PATH_TO_AUTONOMY.md (WS1).
    if result is not None and result.strip():
        return result
    return _extract_by_brace_match(
        source.decode("utf-8", errors="replace"), function_name
    )


def _blank_comments_strings(text: str) -> str:
    """Return a same-length copy with comment/string/char-literal *contents* blanked.

    Positions and length are preserved (blanked chars become spaces, newlines
    kept), so indices found in the blanked copy map 1:1 onto the original. This
    lets boundary/brace scanning ignore delimiters that live inside comments or
    literals (zlib's pre-`inflate` doc comment is full of `;` and `}`).
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        two = text[i : i + 2]
        if two == "//":
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif text[i] in ('"', "'"):
            q = text[i]
            out[i] = " "
            i += 1
            while i < n:
                if text[i] == "\\":
                    out[i] = " "
                    if i + 1 < n:
                        out[i + 1] = " "
                    i += 2
                    continue
                if text[i] == q:
                    out[i] = " "
                    i += 1
                    break
                out[i] = " "
                i += 1
        else:
            i += 1
    return "".join(out)


def _extract_by_brace_match(source_text: str, function_name: str) -> str | None:
    """Recover a C function definition by paren+brace matching when the parser fails.

    Finds `name( ... ) {` (a definition, not a call — a call is followed by `;`
    or an operator, not `{`) and returns from the signature start through the
    body's matching close brace. All scanning runs on a comment/string-blanked
    copy so literal delimiters can't throw off the boundaries; the returned text
    is sliced from the original.
    """
    import re

    clean = _blank_comments_strings(source_text)
    n = len(clean)

    def _match(open_idx: int, opener: str, closer: str) -> int | None:
        depth = 0
        i = open_idx
        while i < n:
            c = clean[i]
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None

    for m in re.finditer(r"\b" + re.escape(function_name) + r"\s*\(", clean):
        paren_open = clean.index("(", m.start())
        paren_close = _match(paren_open, "(", ")")
        if paren_close is None:
            continue
        k = paren_close + 1
        while k < n and clean[k] in " \t\r\n":
            k += 1
        if k >= n or clean[k] != "{":
            continue  # a call or declaration, not a definition
        body_close = _match(k, "{", "}")
        if body_close is None:
            continue
        # Signature start: walk back over the return-type/qualifier tokens
        # (identifiers, `*`, whitespace) on the ORIGINAL text. Anything else — a
        # `;`/`}`/`)` from the previous statement, or the `/` closing a preceding
        # comment — is the boundary. Done on source_text (not `clean`) so a blanked
        # comment's spaces don't let the walk slide into unrelated prior tokens.
        sig_start = m.start()
        while sig_start > 0:
            ch = source_text[sig_start - 1]
            if ch.isalnum() or ch in "_* \t\r\n":
                sig_start -= 1
            else:
                break
        return source_text[sig_start : body_close + 1].strip()
    return None


def _find_identifier(node):
    """Descend declarator nodes to find the innermost identifier."""
    if node.type == "identifier":
        return node
    for child in node.children:
        found = _find_identifier(child)
        if found is not None:
            return found
    return None


def probe_algorithm(
    alg: AlgorithmSpec,
    *,
    source_root: Path,
    llm: AlchemistLLM,
    signature: str,
    struct_context: str = "",
    cached_context=None,
    max_tokens: int = 4000,
    temperature: float = 0.1,
) -> ProbeResult:
    """Probe a single algorithm spec for a C-faithful Rust transliteration.

    Args:
      alg: The AlgorithmSpec whose transliteration is requested.
      source_root: Directory containing the original C source tree
                   (e.g., `subjects/zlib/`). The probe searches this
                   directory using alg.source_files.
      llm: The LLM client. Any AlchemistLLM instance works.
      signature: The target Rust signature the transliteration must match.
      struct_context: Block of shared type definitions already in scope.
    """
    # Locate the C function body.
    c_body = _find_body_in_sources(alg, source_root)
    if c_body is None:
        return ProbeResult(
            algorithm=alg.name,
            success=False,
            error=f"C body not found for {alg.name} in {source_root}",
        )

    prompt = _PROBE_PROMPT.format(
        c_body=c_body,
        signature=signature,
        struct_context=struct_context or "(no shared types referenced)",
        previous_failure="(none)",
    )
    schema = {
        "type": "object",
        "properties": {"content": {"type": "string"}},
        "required": ["content"],
    }
    if cached_context is None:
        cached_context = llm.create_cached_context(system_text=_PROBE_SYSTEM)
    resp: LLMResponse = llm.call_structured(
        messages=[{"role": "user", "content": prompt}],
        tool_name="transliterate",
        tool_schema=schema,
        cached_context=cached_context,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if resp.error:
        return ProbeResult(
            algorithm=alg.name,
            success=False,
            error=f"LLM error: {resp.error}",
        )
    rust = ""
    if resp.structured and "content" in resp.structured:
        rust = (resp.structured.get("content") or "").strip()
    else:
        rust = (resp.content or "").strip()
    if rust.startswith("```"):
        rust = re.sub(r"^```(?:\w+)?\s*", "", rust)
        rust = re.sub(r"```\s*$", "", rust)
    if not rust:
        return ProbeResult(
            algorithm=alg.name,
            success=False,
            error="LLM returned empty transliteration",
        )
    return ProbeResult(
        algorithm=alg.name,
        success=True,
        rust_source=rust,
        notes="transliterated from C source",
    )


_DEFINE_RE = re.compile(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)", re.MULTILINE)


def extract_referenced_macros(source_text: str, body: str) -> str:
    """Return the `#define` directives whose macro NAME appears in `body`.

    C libraries put the load-bearing logic in function-like macros
    (SipHash's SIPROUND, ROTL, U8TO64_LE, dROUNDS) that live OUTSIDE the
    function. Extracting only the function body leaves the model to guess
    what those macros do — and it guesses the round function wrong. Pull the
    full (multi-line, backslash-continued) definition of every macro the
    body references, transitively (a macro that references another macro).
    """
    # Collect every #define with its full multi-line body.
    defines: dict[str, str] = {}
    lines = source_text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        m = _DEFINE_RE.match(lines[i])
        if m:
            name = m.group(1)
            chunk = [lines[i]]
            # Consume backslash-continued continuation lines.
            while chunk[-1].rstrip("\n").endswith("\\") and i + 1 < len(lines):
                i += 1
                chunk.append(lines[i])
            defines[name] = "".join(chunk)
        i += 1

    # Which macros does the body reference? Then close transitively over the
    # macro bodies themselves.
    wanted: list[str] = []
    seen: set[str] = set()
    frontier = [n for n in defines if re.search(rf"\b{re.escape(n)}\b", body)]
    while frontier:
        n = frontier.pop(0)
        if n in seen:
            continue
        seen.add(n)
        wanted.append(n)
        for other in defines:
            if other not in seen and re.search(rf"\b{re.escape(other)}\b", defines[n]):
                frontier.append(other)

    if not wanted:
        return ""
    # Emit in source order for readability.
    ordered = [n for n in defines if n in seen]
    return "".join(defines[n] for n in ordered)


def _find_body_in_sources(alg: AlgorithmSpec, source_root: Path) -> str | None:
    """Search source files for the function's body, enriched with the
    `#define` macros it references (SIPROUND, ROTL, …)."""
    # The spec's source_files may be relative paths or absolute.
    candidate_paths: list[Path] = []
    for sf in alg.source_files or []:
        p = Path(sf)
        if not p.is_absolute():
            p = source_root / sf
        candidate_paths.append(p)
    # Fallback: if no source_files recorded, search every .c file in source_root.
    if not candidate_paths:
        candidate_paths = list(source_root.rglob("*.c"))
    # Try each candidate; accept the first hit.
    for fn_name in alg.source_functions or [alg.name]:
        for path in candidate_paths:
            body = extract_c_function_body(path, fn_name)
            if body:
                try:
                    macros = extract_referenced_macros(
                        path.read_text(encoding="utf-8", errors="replace"), body)
                except OSError:
                    macros = ""
                if macros:
                    return (
                        "/* Macros used by the function below (from the same "
                        "source file) — expand these faithfully: */\n"
                        + macros + "\n" + body
                    )
                return body
    return None


def probe_result_as_reference(probe: ProbeResult, signature: str) -> ReferenceImpl | None:
    """Wrap a probe result as a ReferenceImpl suitable for runtime injection."""
    if not probe.success or not probe.rust_source:
        return None
    return ReferenceImpl(
        algorithm=probe.algorithm,
        variant="probe",
        title=f"{probe.algorithm} (auto-probed from C source)",
        rust_source=probe.rust_source,
        signature=signature,
        notes=probe.notes,
    )
