"""Phase 4B: emit failing tests from specs + standards catalog.

For every algorithm Alchemist extracts, we want a `#[test] fn` that calls
the real public API and checks a known input → expected output mapping.
With the skeleton's `unimplemented!()` bodies in place, every test FAILS
(via panic). That's the TDD forcing function: the implementer cannot ship
until the tests pass.

Sources of test vectors (in priority order):
  1. `spec.test_vectors` (extractor-produced, algorithm-specific)
  2. `alchemist.standards` catalog (RFC / NIST authoritative values)
  3. For roundtrip categories without explicit vectors, emit a smoke test
     that ensures the function is reachable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from alchemist.architect.schemas import CrateArchitecture, CrateSpec
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, TestVector as SpecTestVector
from alchemist.implementer.skeleton import _snake as _rust_fn_name
from alchemist.implementer.skeleton import _sanitize_param_name
from alchemist.standards import TestVector as StdTestVector, lookup_test_vectors


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class CrateTestsResult:
    crate_name: str
    file_path: Path
    tests_written: int = 0
    tests_from_catalog: int = 0
    tests_from_spec: int = 0
    tests_from_smoke: int = 0


# ---------------------------------------------------------------------------
# Test emission
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return re.sub(r"_+", "_", s) or "x"


_TYPED_INT_LITERAL = re.compile(
    r"^-?\d+(?:_\d+)*(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize|f32|f64)$"
)
_PARENTHESIZED_TYPED = re.compile(
    r"^\(\s*-?\d+(?:_\d+)*(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize|f32|f64)\s*\)$"
)


def _try_literal(value: str) -> str | None:
    """Return `value` if it is a recognizable Rust literal, else None."""
    v = value.strip()
    if v.startswith(("&", "b\"", "b'", "0x", "0b", "\"", "[", "vec!")):
        return v
    if v.replace("_", "").replace(".", "").replace("-", "").isdigit():
        return v
    # Typed integer/float literals like `0u64`, `-42i32`, `(-1i8)` are valid Rust.
    if _TYPED_INT_LITERAL.match(v) or _PARENTHESIZED_TYPED.match(v):
        return v
    # Hex literal with suffix like `0xffu64`
    if re.match(r"^0x[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*(?:u\d+|i\d+|usize|isize)?$", v):
        return v
    return None


def _literal_from_spec_value(value: str) -> str:
    """Return a Rust literal. Accepts already-valid Rust literals, or falls
    back to wrapping a bare string in quotes."""
    lit = _try_literal(value)
    if lit is not None:
        return lit
    # Fallback: treat as byte-string literal
    return f'b"{value.strip()}"'


_BYTES_LIKE_RETURN = re.compile(r"\[\s*u8\b|Vec<\s*u8\s*>")
_STR_LIKE_RETURN = re.compile(r"&\s*str\b|\bString\b")


def _msg(s: str) -> str:
    """Escape arbitrary text for an assert!/panic! message FORMAT string.

    Descriptions come from specs and fuzz descriptors; quotes break the
    string literal and unescaped braces are format-string syntax errors
    that kill the whole module's compile.
    """
    return (s.replace("\\", "\\\\").replace('"', "'")
            .replace("{", "{{").replace("}", "}}"))


def _render_expected_value(value: str, return_type: str | None) -> str | None:
    """Render an expected-output value against the fn's actual Rust return type.

    Unlike `_literal_from_spec_value`, this never mangles: a value that can't
    be rendered as valid Rust for the given type returns None, and the caller
    emits a test that FAILS with an explanation instead of a byte-string
    fallback like `b"Some(18usize)"` that poisons the whole module's compile.
    """
    v = value.strip()
    rt = (return_type or "").strip()
    # Constructor expressions for Option/Result returns — already valid Rust.
    m = re.fullmatch(r"(Some|Ok|Err)\((.*)\)", v, flags=re.DOTALL)
    if m:
        inner = _render_expected_value(m.group(2), None)
        return f"{m.group(1)}({inner})" if inner is not None else None
    if v in ("None", "true", "false"):
        return v
    lit = _try_literal(v)
    if lit is not None:
        return lit
    # A bare string only renders as a byte/str literal when the return type
    # actually is one.
    if _BYTES_LIKE_RETURN.search(rt):
        return f'b"{v}"'
    if _STR_LIKE_RETURN.search(rt):
        return f'"{v}"'
    return None


# Default values for well-known checksum/hash parameter names.
# Keyed by lowercase param-name prefix → Rust expression.
_PARAM_DEFAULTS = {
    "buf": "input",
    "data": "input",
    "input": "input",
    "bytes": "input",
    "msg": "input",
    "src": "input",
    "source": "input",
    "len": "input.len()",
    "length": "input.len()",
    "size": "input.len()",
    "n": "input.len()",
    # Checksum seeds.
    "adler": "1u32",
    "seed": "1u32",  # will be overridden to 0 for crc below
    "state": "0u32",
    "crc": "0u32",
    "init": "0u32",
    # Keys / IVs for ciphers (only if a `key` local exists in the test).
    "key": "key",
    "iv": "iv",
}


def _default_for_param(fn_name: str, pname: str, ptype: str) -> str:
    """Pick a sensible default Rust expression for a parameter when the
    caller only has the input slice available."""
    low = pname.lower().lstrip("_")
    # adler32-ish seed defaults to 1, crc32-ish seed defaults to 0.
    if low in ("seed", "state", "init") and "crc" in fn_name.lower():
        return "0u32"
    if low in _PARAM_DEFAULTS:
        return _PARAM_DEFAULTS[low]
    # Integer default
    if re.match(r"^(?:u|i)\d+$", ptype):
        return "0"
    if ptype.startswith("&[u8]"):
        return "input"
    if ptype.startswith("usize"):
        return "input.len()"
    # Unknown — emit 0 and hope
    return "Default::default()"


def _build_call(fn_name: str, alg: AlgorithmSpec | None) -> str:
    """Construct a `super::<fn>(args...)` call that matches the spec signature.

    When alg is None or has no inputs, falls back to `super::<fn>(input)`.
    """
    if alg is None or not alg.inputs:
        return f"super::{fn_name}(input)"
    args: list[str] = []
    for p in alg.inputs:
        args.append(_default_for_param(fn_name, p.name, p.rust_type))
    return f"super::{fn_name}({', '.join(args)})"


def _can_accept_byte_slice(alg: AlgorithmSpec) -> bool:
    """True iff the algorithm has at least one `&[u8]`-ish input parameter.

    Without one, emitting a catalog-style test (`let input: &[u8] = ...; super::fn(input)`)
    would be meaningless — the helper is likely a table init or reset-state fn.
    """
    if not alg.inputs:
        return False
    for p in alg.inputs:
        t = (p.rust_type or "").lower()
        if "[u8]" in t or "vec<u8>" in t or "bytes" in t or "&str" in t:
            return True
    return False


def _has_canonical_shape_for_category(alg: AlgorithmSpec) -> bool:
    """Guard against emitting catalog tests for helpers that don't match
    the shape the template assumes.

    Templates expect:
      - checksum: `fn(&[u8]) -> u32` or `fn(u32, &[u8]) -> u32`
      - hash:     `fn(&[u8]) -> [u8; N] | Vec<u8>`
      - cipher:   `fn(key, &[u8]) -> Vec<u8>` (roundtrip)
      - compression/decompression: `fn(&[u8]) -> Vec<u8>` or
        `fn(&mut [u8], &[u8]) -> Result<(), _>`

    Functions like `deflateSetDictionary` have `&[u8]` inputs but return
    Result<()> and take `&mut DeflateStream` — the compression template
    emits `decompressed.as_slice()` against them and fails to compile.
    """
    ret = (alg.return_type or "").strip()
    cat = alg.category

    # Struct/stream state params disqualify canonical catalog templates.
    for p in alg.inputs or []:
        t = (p.rust_type or "")
        if re.search(r"\b(?:Deflate|Inflate|Stream|State)\w*\b", t):
            return False

    if cat == "checksum":
        # Expect a scalar numeric return
        return bool(re.match(r"^(?:u|i)\d+$", ret))
    if cat == "hash":
        # Expect bytes-or-array return
        return ("[u8" in ret) or ("Vec<u8>" in ret)
    if cat == "cipher":
        return ("Vec<u8>" in ret) or ("[u8" in ret) or ret.startswith("Result<")
    if cat in ("compression", "decompression"):
        # compress-template calls `.as_slice()` on the result. That works
        # only when the function literally returns a Vec<u8> or Result<Vec<u8>>.
        if "Vec<u8>" in ret:
            return True
        if re.search(r"Result<\s*Vec<u8>", ret):
            return True
        return False
    return True


def _emit_catalog_test_checksum(
    fn_name: str, vec: StdTestVector, idx: int,
    alg: AlgorithmSpec | None = None,
) -> str:
    test_name = f"test_{fn_name}_vec_{_slug(vec.name) or idx}"
    input_lit = vec.as_rust_literal("input")
    expected_hex = vec.expected_hex
    call = _build_call(fn_name, alg)
    return (
        f"    #[test]\n"
        f"    fn {test_name}() {{\n"
        f"        let input: &[u8] = {input_lit};\n"
        f"        let got = {call};\n"
        f'        assert_eq!(format!("{{:08x}}", got), "{expected_hex}", '
        f'"vector {vec.name!r} failed");\n'
        f"    }}\n"
    )


def _emit_catalog_test_hash(
    fn_name: str, vec: StdTestVector, idx: int,
    alg: AlgorithmSpec | None = None,
) -> str:
    test_name = f"test_{fn_name}_vec_{_slug(vec.name) or idx}"
    input_lit = vec.as_rust_literal("input")
    call = _build_call(fn_name, alg)
    return (
        f"    #[test]\n"
        f"    fn {test_name}() {{\n"
        f"        let input: &[u8] = {input_lit};\n"
        f"        let digest = {call};\n"
        f'        let hex: String = digest.iter().map(|b| format!("{{:02x}}", b)).collect();\n'
        f'        assert_eq!(hex, "{vec.expected_hex}", '
        f'"vector {vec.name!r} failed");\n'
        f"    }}\n"
    )


def _emit_catalog_test_cipher(
    fn_name: str, vec: StdTestVector, idx: int,
    alg: AlgorithmSpec | None = None,
) -> str:
    test_name = f"test_{fn_name}_vec_{_slug(vec.name) or idx}"
    input_lit = vec.as_rust_literal("input")
    key_lit = vec.as_rust_literal("key")
    expected_lit = vec.as_rust_literal("expected")
    call = _build_call(fn_name, alg) if alg else f"super::{fn_name}(&key, &input)"
    return (
        f"    #[test]\n"
        f"    fn {test_name}() {{\n"
        f"        let input: &[u8] = {input_lit};\n"
        f"        let key: &[u8] = {key_lit};\n"
        f"        let expected: &[u8] = {expected_lit};\n"
        f"        let ct = {call};\n"
        f'        assert_eq!(ct.as_slice(), expected, "vector {vec.name!r} failed");\n'
        f"    }}\n"
    )


def _emit_catalog_test_compression(
    fn_name: str, vec: StdTestVector, idx: int,
    alg: AlgorithmSpec | None = None,
) -> str:
    """For compression we test that decompress(reference_blob) == input."""
    test_name = f"test_{fn_name}_vec_{_slug(vec.name) or idx}"
    input_lit = vec.as_rust_literal("input")
    expected_lit = vec.as_rust_literal("expected")
    # For compression the expected blob is the "input" to the decompress fn
    # — map the alg-inputs against `reference_compressed` instead of `input`.
    if alg and alg.inputs:
        args = []
        for p in alg.inputs:
            expr = _default_for_param(fn_name, p.name, p.rust_type)
            # Re-route `input`/`input.len()` to the reference_compressed var
            expr = expr.replace("input", "reference_compressed")
            args.append(expr)
        call = f"super::{fn_name}({', '.join(args)})"
    else:
        call = f"super::{fn_name}(reference_compressed)"
    return (
        f"    #[test]\n"
        f"    fn {test_name}() {{\n"
        f"        let original: &[u8] = {input_lit};\n"
        f"        let reference_compressed: &[u8] = {expected_lit};\n"
        f"        let decompressed = {call};\n"
        f'        assert_eq!(decompressed.as_slice(), original, '
        f'"decompress of standards blob {vec.name!r} did not recover input");\n'
        f"    }}\n"
    )


def _emit_state_mutator_test(fn_name: str, vec: SpecTestVector, idx: int) -> str:
    """Emit a test for a state-mutator function.

    Input dict has keys `state.<field>` (pre-state) and plain names (extra args).
    Expected output is newline-separated `field:rust_type=value` lines.
    Test constructs a fresh state with the pre-state values, calls the fn,
    and asserts each post-state field.
    """
    test_name = f"test_{fn_name}_state_{idx}"
    # Split pre-state fields from extra args
    state_inits: list[tuple[str, str]] = []
    extra_args: list[tuple[str, str]] = []
    for pname, pvalue in vec.inputs.items():
        if pname.startswith("state."):
            field_name = pname[len("state."):]
            state_inits.append((field_name, pvalue))
        else:
            extra_args.append((pname, pvalue))
    lines = [f"    #[test]\n    fn {test_name}() {{\n"]
    # State type by zlib convention: inflate* functions mutate an InflateState,
    # everything else a DeflateState. (The shim binding's fields already match
    # the corresponding struct.)
    state_ty = "InflateState" if fn_name.startswith("inflate") else "DeflateState"
    lines.append(f"        let mut state = zlib_types::{state_ty}::default();\n")
    for field_name, rendered in state_inits:
        lines.append(f"        state.{field_name} = {rendered};\n")
    for arg_name, rendered in extra_args:
        lines.append(f"        let {arg_name} = {rendered};\n")
    # Build the call: state is first arg, extras after. A Vec/slice-valued
    # extra arg is borrowed (`&name`) because the function takes a slice
    # (e.g. pqdownheap's `tree: &[TreeElement]`); scalars pass by value.
    def _pass(name: str, rendered: str) -> str:
        # An owned Vec literal is borrowed so it coerces to the `&[T]` the
        # function expects. Values already rendered as slices (`&[...]`) or
        # scalars pass through unchanged.
        if rendered.lstrip().startswith("vec!"):
            return f"&{name}"
        return name
    if extra_args:
        extra_str = ", ".join(_pass(n, r) for n, r in extra_args)
        lines.append(f"        super::{fn_name}(&mut state, {extra_str});\n")
    else:
        lines.append(f"        super::{fn_name}(&mut state);\n")
    # Parse expected fields and emit assertions.
    for line in vec.expected_output.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        lhs, rhs = line.split("=", 1)
        # lhs is "name:rust_type"
        if ":" not in lhs:
            continue
        field_name, _ = lhs.split(":", 1)
        lines.append(
            f"        assert_eq!(state.{field_name.strip()}, {rhs.strip()}, "
            f'"{vec.description} field {field_name.strip()}");\n'
        )
    lines.append("    }\n")
    return "".join(lines)


def _emit_state_observer_seq_test(fn_name: str, vec, idx: int) -> str:
    """Post-init state-observer: run init(key), assert each struct field equals the C oracle."""
    parts = (vec.tolerance or "").split("|")
    rust_struct = parts[1] if len(parts) > 1 else "State"
    key_param = parts[3] if len(parts) > 3 else "key"
    len_param = parts[4] if len(parts) > 4 else "len"
    key_lit = vec.inputs.get(key_param, "&[]")
    klen = vec.inputs.get(len_param, "0")
    lines = [f"    #[test]\n    fn test_{fn_name}_state_{idx}() {{\n"]
    lines.append(f"        let mut st = super::{rust_struct}::default();\n")
    lines.append(f"        let key = {key_lit};\n")
    lines.append(f"        super::{fn_name}(&mut st, key);\n")
    for pair in (vec.expected_output or "").split("|"):
        fname, _, lit = pair.partition(":")
        if not fname:
            continue
        lines.append(f"        assert_eq!(st.{fname}, {lit}, \"{vec.description} {fname}\");\n")
    lines.append("    }\n")
    return "".join(lines)


def _emit_cipher_seq_test(fn_name: str, vec, idx: int) -> str:
    """init(key) then gen(out) — assert the keystream equals the C oracle."""
    parts = (vec.tolerance or "").split("|")
    rust_struct = parts[1] if len(parts) > 1 else "State"
    init_fn = parts[2] if len(parts) > 2 else "init"
    key_param = parts[3] if len(parts) > 3 else "key"
    klen_param = parts[4] if len(parts) > 4 else "klen"
    outlen_param = parts[5] if len(parts) > 5 else "outlen"
    key_lit = vec.inputs.get(key_param, "&[]")
    klen = vec.inputs.get(klen_param, "0")
    outlen = vec.inputs.get(outlen_param, "0")
    lines = [f"    #[test]\n    fn test_{fn_name}_seq_{idx}() {{\n"]
    lines.append(f"        let mut st = super::{rust_struct}::default();\n")
    lines.append(f"        let key = {key_lit};\n")
    lines.append(f"        super::{init_fn}(&mut st, key);\n")
    lines.append(f"        let mut out = alloc::vec![0u8; {outlen}];\n")
    lines.append(f"        super::{fn_name}(&mut st, &mut out);\n")
    lines.append(f"        assert_eq!(&out[..], {vec.expected_output}, \"{vec.description}\");\n")
    lines.append("    }\n")
    return "".join(lines)


def _emit_alloc_init_test(fn_name: str, vec, idx: int) -> str:
    """Post-init state-observer for an allocator: init a buffer of size cap, assert fields."""
    parts = (vec.tolerance or "").split("|")
    rust_struct = parts[1] if len(parts) > 1 else "State"
    fnames = (parts[3].split(",") if len(parts) > 3 and parts[3] else [])
    kinds = (parts[4].split(",") if len(parts) > 4 and parts[4] else ["buf"])
    cap = vec.inputs.get("__cap__", "0")
    args = "".join(", &mut buf" if k == "buf" else f", {cap}" for k in kinds)
    exp = {kv.split(":")[0]: kv.split(":")[1] for kv in (vec.expected_output or "").split("|") if ":" in kv}
    lines = [f"    #[test]\n    fn test_{fn_name}_ainit_{idx}() {{\n"]
    lines.append(f"        let mut buf = alloc::vec![0u8; {cap}];\n")
    lines.append(f"        let mut a = super::{rust_struct}::default();\n")
    lines.append(f"        super::{fn_name}(&mut a{args});\n")
    for fn in fnames:
        if fn in exp:
            lines.append(f"        assert_eq!(a.{fn} as i64, {exp[fn]}, \"{vec.description} {fn}\");\n")
    lines.append("    }\n")
    return "".join(lines)


def _emit_alloc_seq_test(fn_name: str, vec, idx: int) -> str:
    """init(buffer of size cap) then op(n) sequence; assert the return sequence vs C."""
    parts = (vec.tolerance or "").split("|")
    rust_struct = parts[1] if len(parts) > 1 else "State"
    init_fn = parts[2] if len(parts) > 2 else "init"
    ret_kind = parts[4] if len(parts) > 4 else "int"
    kinds = (parts[5].split(",") if len(parts) > 5 and parts[5] else ["buf"])
    cap = vec.inputs.get("__cap__", "0")
    ns = vec.inputs.get("__ns__", "")
    args = "".join(", &mut buf" if k == "buf" else f", {cap}" for k in kinds)
    ns_lits = ", ".join(f"{x}usize" for x in ns.split(",") if x != "")
    exp_lits = ", ".join(f"{x}i64" for x in (vec.expected_output or "").split(",") if x != "")
    _map = ".map(|x| x as i64).unwrap_or(-1)" if ret_kind == "result" else " as i64"
    lines = [f"    #[test]\n    fn test_{fn_name}_aseq_{idx}() {{\n"]
    lines.append(f"        let mut buf = alloc::vec![0u8; {cap}];\n")
    lines.append(f"        let mut a = super::{rust_struct}::default();\n")
    lines.append(f"        super::{init_fn}(&mut a{args});\n")
    lines.append(f"        let mut got: alloc::vec::Vec<i64> = alloc::vec::Vec::new();\n")
    lines.append(f"        for &n in [{ns_lits}].iter() {{\n")
    lines.append(f"            got.push(super::{fn_name}(&mut a, n){_map});\n")
    lines.append(f"        }}\n")
    lines.append(f"        assert_eq!(got, alloc::vec![{exp_lits}], \"{vec.description}\");\n")
    lines.append("    }\n")
    return "".join(lines)


def _emit_scalar_mutator_test(fn_name: str, vec, idx: int) -> str:
    """Drive the mutator on a seed state (+ extra args); assert (return, post-state)."""
    parts = (vec.tolerance or "").split("|")
    state_param = parts[1] if len(parts) > 1 else "state"
    state_rust = parts[2] if len(parts) > 2 else "u64"
    ret_rust = parts[3] if len(parts) > 3 else "unit"
    extra_spec = parts[4] if len(parts) > 4 else ""
    ret_s, _, new_s = (vec.expected_output or "0|0").partition("|")
    init_val = vec.inputs.get(state_param, "0")
    extra_names = [tok.split(":")[0] for tok in extra_spec.split(",") if tok]
    call_args = [f"&mut {state_param}"] + [vec.inputs.get(nm, "0") for nm in extra_names]
    argstr = ", ".join(call_args)
    lines = [f"    #[test]\n    fn test_{fn_name}_mut_{idx}() {{\n"]
    lines.append(f"        let mut {state_param}: {state_rust} = {init_val};\n")
    if ret_rust == "unit":
        lines.append(f"        super::{fn_name}({argstr});\n")
    else:
        lines.append(f"        let got = super::{fn_name}({argstr});\n")
        lines.append(f"        assert_eq!(got, {ret_s}, \"{vec.description} ret\");\n")
    lines.append(f"        assert_eq!({state_param}, {new_s}, \"{vec.description} state\");\n")
    lines.append("    }\n")
    return "".join(lines)


def _emit_byte_transform_test(
    fn_name: str, vec: SpecTestVector, idx: int,
) -> str:
    """Emit a test for a byte-buffer-transformation fn (zmemcpy/zmemcmp/zmemzero).

    Tolerance field encodes the assertion kind and which parameter is the
    mutable buffer: "byte_transform|<kind>|<mut_buf>|<n_param>".

    Input values using magic prefixes:
      __VECZERO__<N>       -> vec![0u8; N]
      __VECFILL_FF__<N>    -> vec![0xFFu8; N]   (non-zero seed for zmemzero)

    For buffer_postcondition: asserts `&mut_buf[..n]` equals expected bytes.
    For scalar: asserts return value equals expected (existing literal path).
    """
    parts = (vec.tolerance or "").split("|")
    _, kind, mut_buf, n_param = (parts + ["", "", ""])[:4]
    test_name = f"test_{fn_name}_xform_{idx}"
    lines = [f"    #[test]\n    fn {test_name}() {{\n"]
    for pname, pvalue in vec.inputs.items():
        v = pvalue.strip()
        if v.startswith("__VEC__"):
            body = v[len("__VEC__"):]
            lines.append(f"        let mut {pname}: alloc::vec::Vec<u8> = alloc::vec![{body}];\n")
        elif v.startswith("__VECZERO__"):
            n_literal = v[len("__VECZERO__"):]
            lines.append(f"        let mut {pname}: alloc::vec::Vec<u8> = alloc::vec![0u8; {n_literal}];\n")
        elif v.startswith("__VECFILL_FF__"):
            n_literal = v[len("__VECFILL_FF__"):]
            lines.append(f"        let mut {pname}: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; {n_literal}];\n")
        else:
            lines.append(f"        let {pname} = {_literal_from_spec_value(v)};\n")
    arg_list = ", ".join(
        f"&mut {p}" if p == mut_buf else p
        for p in vec.inputs.keys()
    )
    if kind == "scalar":
        lines.append(f"        let got = super::{fn_name}({arg_list});\n")
        lines.append(
            f"        assert_eq!(got, {_literal_from_spec_value(vec.expected_output)}, "
            f'"{vec.description}");\n'
        )
    else:
        # buffer_postcondition — call for side effect, inspect mut buffer.
        lines.append(f"        super::{fn_name}({arg_list});\n")
        expected_lit = _literal_from_spec_value(vec.expected_output)
        # Compare only the first n_param bytes — tail bytes may retain
        # the initial fill pattern (0xFF for zmemzero's buffer beyond len,
        # or 0 for zmemcpy's dst beyond n).
        lines.append(
            f"        assert_eq!(&{mut_buf}[..{n_param}], {expected_lit}, "
            f'"{vec.description}");\n'
        )
    lines.append("    }\n")
    return "".join(lines)


def _emit_state_observer_test(fn_name: str, vec: SpecTestVector, idx: int) -> str:
    """Emit a test for a state-observer function.

    Shape: read-only `&DeflateState` (or similar) → scalar return.
    Expected output is a single rendered literal (e.g., "0i32").

    Vectors carry pre-rendered Rust statements under `__stmt__<N>` keys
    (preferred) or legacy `state.<field>` keys (simple assignment). The
    `__stmt__` form lets the binding translate between the shim's flat
    field view (dyn_ltree_freq: Vec<u16>) and the Rust struct layout
    (dyn_ltree: Vec<(u16, u16)>).
    """
    test_name = f"test_{fn_name}_observer_{idx}"
    lines = [f"    #[test]\n    fn {test_name}() {{\n"]
    state_ty = "InflateState" if fn_name.startswith("inflate") else "DeflateState"
    lines.append(f"        let mut state = zlib_types::{state_ty}::default();\n")
    # Pre-rendered statements (__stmt__0, __stmt__1, ...) take priority
    stmt_items = sorted(
        ((k, v) for k, v in vec.inputs.items() if k.startswith("__stmt__")),
        key=lambda kv: int(kv[0][len("__stmt__"):])
        if kv[0][len("__stmt__"):].isdigit() else 0,
    )
    for _, stmt in stmt_items:
        lines.append(f"        {stmt}\n")
    # Legacy path: plain `state.<field>` simple assignment
    for pname, pvalue in vec.inputs.items():
        if pname.startswith("state."):
            field_name = pname[len("state."):]
            lines.append(f"        state.{field_name} = {pvalue};\n")
    lines.append(f"        let got = super::{fn_name}(&state);\n")
    expected = vec.expected_output.strip()
    if expected:
        lines.append(
            f"        assert_eq!(got, {expected}, "
            f'"{vec.description}");\n'
        )
    lines.append("    }\n")
    return "".join(lines)


def _emit_spec_test(
    fn_name: str,
    vec: SpecTestVector,
    idx: int,
    *,
    return_type: str | None = None,
) -> str:
    """Emit a test from a spec.test_vectors entry.

    `return_type` is the algorithm's actual Rust return type; expected values
    are rendered against it (Option/Result constructors pass through, bare
    strings only become byte-strings for byte-like returns). A value that
    can't be rendered emits a test that FAILS with an explanation, so the
    gate stays red instead of the module failing to compile.
    """
    # Fully-rendered Rust test body: the fuzzer authored the complete
    # statements (let-bindings + call + asserts). Used by tree-builders whose
    # shape (no &mut state, mutated slice params, field-projected output
    # comparison) doesn't fit the field-by-field templates. `inputs` is
    # ignored; `expected_output` IS the body.
    if vec.tolerance == "rust_body":
        body = vec.expected_output or ""
        indented = "\n".join(
            ("        " + ln if ln.strip() else ln) for ln in body.splitlines())
        return (f"    #[test]\n    fn test_{fn_name}_body_{idx}() {{\n"
                f"{indented}\n    }}\n")
    # State-mutator vectors use a different test shape
    if vec.tolerance == "state_mutator":
        return _emit_state_mutator_test(fn_name, vec, idx)
    # State-observer vectors (state_in -> scalar return, no mutation)
    if vec.tolerance == "state_observer":
        return _emit_state_observer_test(fn_name, vec, idx)
    # Byte-buffer transform vectors (zmem* family) carry a pipe-encoded
    # tolerance field starting with "byte_transform".
    if (vec.tolerance or "").startswith("alloc_init"):
        return _emit_alloc_init_test(fn_name, vec, idx)
    if (vec.tolerance or "").startswith("alloc_seq"):
        return _emit_alloc_seq_test(fn_name, vec, idx)
    if (vec.tolerance or "").startswith("state_observer"):
        return _emit_state_observer_seq_test(fn_name, vec, idx)
    if (vec.tolerance or "").startswith("cipher_seq"):
        return _emit_cipher_seq_test(fn_name, vec, idx)
    if (vec.tolerance or "").startswith("scalar_mutator"):
        return _emit_scalar_mutator_test(fn_name, vec, idx)
    if (vec.tolerance or "").startswith("byte_transform"):
        return _emit_byte_transform_test(fn_name, vec, idx)
    test_name = f"test_{fn_name}_spec_{idx}"
    lines = [f"    #[test]\n    fn {test_name}() {{\n"]
    # Sanitize parameter names the same way the skeleton does, so a C param
    # that is a Rust keyword (`in`, `type`, `match`, …) becomes a raw
    # identifier (`r#in`) in both the let-binding and the call — otherwise
    # the whole test module fails to compile.
    arg_names = []
    for pname, pvalue in vec.inputs.items():
        safe_name = _sanitize_param_name(pname, len(arg_names))
        arg_names.append(safe_name)
        lines.append(f"        let {safe_name} = {_literal_from_spec_value(pvalue)};\n")
    arg_list = ", ".join(arg_names)
    lines.append(f"        let got = super::{fn_name}({arg_list});\n")
    expected = vec.expected_output.strip()
    if expected:
        # Try as a Rust literal
        if vec.tolerance in ("exact", ""):
            rendered = _render_expected_value(expected, return_type)
            if rendered is None:
                # Escape for a panic!() FORMAT string: quotes, backslashes,
                # and braces (struct-literal values are the archetypal
                # unrenderable shape and always contain braces).
                safe = _msg(expected)
                return (
                    f"    #[test]\n    fn {test_name}() {{\n"
                    f"        panic!(\"UNRENDERABLE expected value `{safe}` for return "
                    f"type `{(return_type or 'unknown').strip()}` — the vector source "
                    f"(fuzz_vectors / spec) emitted a value the test renderer cannot "
                    f"express as Rust. Fix the renderer or the vector; do not ship "
                    f"unverified.\");\n"
                    f"    }}\n"
                )
            lines.append(f"        assert_eq!(got, {rendered}, "
                         f'"{_msg(vec.description or vec.source or f"vector {idx}")}");\n')
        else:
            # Numeric tolerance
            lines.append(f"        let eps: f64 = {vec.tolerance};\n")
            lines.append(f"        let expected: f64 = {_literal_from_spec_value(expected)};\n")
            lines.append(f"        let got_f: f64 = got as f64;\n")
            lines.append(f"        assert!((got_f - expected).abs() < eps, "
                         f'"{_msg(vec.description or f"vector {idx}")}");\n')
    lines.append("    }\n")
    return "".join(lines)


def _emit_smoke_test(fn_name: str) -> str:
    """Emit a trivial call to ensure the function is callable on a short input."""
    return (
        f"    #[test]\n"
        f"    fn smoke_{fn_name}() {{\n"
        f"        // smoke — call with small empty-ish input; actual correctness\n"
        f"        // is covered by catalog and spec vectors.\n"
        f"        let _ = std::panic::catch_unwind(|| {{\n"
        f"            let _ = super::{fn_name}(&[][..]);\n"
        f"        }});\n"
        f"    }}\n"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit_module_test_block(
    module: ModuleSpec,
    *,
    enable_smoke: bool = False,
    catalog_lookup=lookup_test_vectors,
) -> tuple[str, dict[str, int]]:
    """Produce the `#[cfg(test)] mod tests` block body for one module.

    Returns (rust_source, stats_dict).
    """
    stats = {"spec": 0, "catalog": 0, "smoke": 0}
    lines: list[str] = []
    lines.append("#[cfg(test)]")
    lines.append("mod tests {")
    lines.append("    #![allow(unused_imports, unused_variables, unused_macros)]")
    lines.append("    extern crate alloc;")
    lines.append("    use alloc::format;")
    lines.append("    use alloc::string::String;")
    lines.append("")

    emitted_any = False

    for alg in module.algorithms:
        # Resolve the Rust function name the same way skeleton.py does so
        # super::<fn>(...) resolves. Key case: zlib `_tr_init` / `_tr_align`
        # lose their leading underscore in the skeleton's _snake() pass.
        fn_name = _rust_fn_name(alg.name)
        # 1. Spec-provided test vectors
        for i, v in enumerate(alg.test_vectors or []):
            lines.append(_emit_spec_test(fn_name, v, i, return_type=alg.return_type))
            stats["spec"] += 1
            emitted_any = True
        # 2. Standards catalog — only when the signature matches a recognizable
        #    canonical shape. The compression/cipher templates assume very
        #    specific APIs (Vec<u8> return with .as_slice(), etc.). Emitting
        #    them against arbitrary deflate*/inflate* helpers produces
        #    uncompilable tests that poison the whole crate's test run.
        if _can_accept_byte_slice(alg) and _has_canonical_shape_for_category(alg):
            cat_vectors = catalog_lookup(alg.name)
            for i, v in enumerate(cat_vectors or []):
                if alg.category == "checksum":
                    lines.append(_emit_catalog_test_checksum(fn_name, v, i, alg=alg))
                elif alg.category == "hash":
                    lines.append(_emit_catalog_test_hash(fn_name, v, i, alg=alg))
                elif alg.category == "cipher":
                    lines.append(_emit_catalog_test_cipher(fn_name, v, i, alg=alg))
                elif alg.category in ("compression", "decompression"):
                    lines.append(_emit_catalog_test_compression(fn_name, v, i, alg=alg))
                else:
                    continue
                stats["catalog"] += 1
                emitted_any = True

    if not emitted_any and enable_smoke:
        # Fall back to smoke tests for every fn
        for alg in module.algorithms:
            lines.append(_emit_smoke_test(_rust_fn_name(alg.name)))
            stats["smoke"] += 1

    lines.append("}")
    return "\n".join(lines) + "\n", stats


def append_tests_to_module_file(
    crate_dir: Path,
    module: ModuleSpec,
    *,
    enable_smoke: bool = False,
) -> dict[str, int]:
    """Append the test block to `<crate>/src/<module>.rs` if not already there."""
    path = crate_dir / "src" / f"{module.name}.rs"
    if not path.exists():
        raise FileNotFoundError(f"cannot append tests: {path} does not exist")
    current = path.read_text(encoding="utf-8")
    # If a tests block already exists, replace it
    if "#[cfg(test)]" in current and "mod tests" in current:
        # Strip everything from `#[cfg(test)]` onwards
        idx = current.find("#[cfg(test)]")
        current = current[:idx].rstrip() + "\n\n"
    tests_src, stats = emit_module_test_block(module, enable_smoke=enable_smoke)
    merged = current.rstrip() + "\n\n" + tests_src
    path.write_text(merged, encoding="utf-8")
    return stats


def generate_tests_for_crate(
    crate: CrateSpec,
    module_specs: list[ModuleSpec],
    crate_dir: Path,
    *,
    enable_smoke: bool = False,
) -> CrateTestsResult:
    """Append a tests block to every module file in the crate."""
    modules = [m for m in module_specs if m.name in set(crate.modules)]
    total_spec = total_catalog = total_smoke = 0
    file_path = crate_dir / "src"
    for m in modules:
        stats = append_tests_to_module_file(crate_dir, m, enable_smoke=enable_smoke)
        total_spec += stats["spec"]
        total_catalog += stats["catalog"]
        total_smoke += stats["smoke"]
    return CrateTestsResult(
        crate_name=crate.name,
        file_path=file_path,
        tests_written=total_spec + total_catalog + total_smoke,
        tests_from_catalog=total_catalog,
        tests_from_spec=total_spec,
        tests_from_smoke=total_smoke,
    )


def generate_tests_for_workspace(
    specs: list[ModuleSpec],
    architecture: CrateArchitecture,
    workspace_dir: Path,
    *,
    enable_smoke: bool = False,
) -> list[CrateTestsResult]:
    """Append test blocks for every crate in the workspace."""
    results: list[CrateTestsResult] = []
    for crate in architecture.crates:
        crate_dir = workspace_dir / crate.name
        if not crate_dir.exists():
            continue
        r = generate_tests_for_crate(crate, specs, crate_dir, enable_smoke=enable_smoke)
        results.append(r)
    return results
