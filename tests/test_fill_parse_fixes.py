"""Regression tests for three fill-path bugs that stacked to sink the smaz
translation (all three: /tmp/smaz/.alchemist/output/smaz/src/smaz.rs).

Bug 1: JSON string escapes written literally into the .rs (`\n`, `\"`).
Bug 2: C params named with a Rust keyword (`in`) carried verbatim -> won't compile.
Bug 3: consts-in-scope reporter blind to mixed-case carried consts -> model
       hallucinates the codebook instead of using the carried one.
"""

from __future__ import annotations

from alchemist.implementer.tdd_generator import (
    TDDGenerator,
    _unwrap_llm_schema_leak,
    _extract_json_string_field,
    _json_unescape_lenient,
)
from alchemist.implementer.skeleton import _sanitize_param_name


# --------------------------------------------------------------------------
# Bug 1 — JSON-encoded fill responses must decode to real newlines/quotes,
# and must NOT corrupt Rust `\xNN` byte-string literals.
# --------------------------------------------------------------------------

def test_extract_json_string_field_decodes_escapes():
    blob = r'{"content": "pub fn f() {\n    let x = 1;\n    x\n}"} trailing junk'
    v = _extract_json_string_field(blob, "content")
    assert v is not None
    assert "\\n" not in v          # no literal backslash-n survives
    assert v.count("\n") == 3      # three real newlines
    assert "pub fn f()" in v


def test_extract_json_string_field_preserves_byte_literals():
    # A Rust byte-string literal `b"\x02s"` is JSON-encoded as `b\"\\x02s\"`.
    blob = r'{"content": "pub const T: [&[u8]; 1] = [b\"\\x02s\"];"}'
    v = _extract_json_string_field(blob, "content")
    assert v is not None
    assert r'b"\x02s"' in v         # backslash-x-0-2 preserved exactly


def test_unwrap_schema_leak_recovers_from_broken_json():
    # Whole-blob json.loads fails (unescaped control char), but the content
    # field is still recoverable and must come back with real newlines.
    blob = '{"content": "pub fn g() {\\n    0\\n}", "note": "un\x01escaped"}'
    out = _unwrap_llm_schema_leak(blob)
    assert "pub fn g()" in out
    assert "\\n" not in out
    assert out.count("\n") >= 1


def test_json_unescape_lenient_fixes_literal_newlines_keeps_byte_literals():
    corrupt = r'pub fn f() {\n    let t = b"\x02\xb6";\n}'
    fixed = _json_unescape_lenient(corrupt)
    assert fixed.count("\n") == 2          # \n -> real newlines
    assert r'b"\x02\xb6"' in fixed          # \x escapes untouched


def test_unwrap_last_resort_repairs_literal_escapes():
    # A JSON-shaped blob whose structure is malformed enough that both
    # json.loads and field-extraction fail, but a `pub fn` with literal
    # escapes is still present — the last-resort path must repair the escapes.
    corrupt = r'{ malformed :: pub fn h(in_: &[u8]) -> u32 {\n    0\n}'
    out = _unwrap_llm_schema_leak(corrupt)
    assert "pub fn h" in out
    assert "\\n" not in out
    assert out.count("\n") == 2


# --------------------------------------------------------------------------
# Bug 2 — Rust keyword param names must be made legal identifiers.
# --------------------------------------------------------------------------

def test_sanitize_keyword_param_names():
    assert _sanitize_param_name("in", 0) == "r#in"
    assert _sanitize_param_name("type", 1) == "r#type"
    assert _sanitize_param_name("match", 2) == "r#match"
    assert _sanitize_param_name("inlen", 3) == "inlen"     # not a keyword
    assert _sanitize_param_name("out", 4) == "out"


def test_signature_rendering_uses_safe_param_names():
    # `_signature_for` only touches p.name / p.rust_type / alg.name /
    # return_type / inputs — a lightweight stand-in exercises the fix without
    # coupling to the real schema constructor.
    from types import SimpleNamespace
    alg = SimpleNamespace(
        name="smaz_decompress",
        inputs=[SimpleNamespace(name="in", rust_type="&[u8]"),
                SimpleNamespace(name="out", rust_type="&[u8]")],
        return_type="Vec<u8>",
    )
    gen = TDDGenerator.__new__(TDDGenerator)  # no __init__ needed for pure method
    sig = TDDGenerator._signature_for(gen, alg)
    assert "r#in: &[u8]" in sig
    assert "(in:" not in sig


# --------------------------------------------------------------------------
# Bug 3 — the consts-in-scope reporter must see mixed-case carried consts.
# --------------------------------------------------------------------------

def test_consts_in_scope_detects_mixed_case():
    module = (
        "pub const Smaz_cb: [&[u8]; 241] = [];\n"
        "pub const Smaz_rcb: [&[u8]; 254] = [];\n"
        "pub const CRC32_TABLE: [u32; 256] = [];\n"
        "static readyFlag: bool = false;\n"
    )
    scope = TDDGenerator._consts_in_scope(module)
    assert "Smaz_cb" in scope
    assert "Smaz_rcb" in scope
    assert "CRC32_TABLE" in scope     # caps still works
    assert "readyFlag" in scope


def test_consts_in_scope_empty_when_none():
    assert "none" in TDDGenerator._consts_in_scope("pub fn f() {}").lower()
