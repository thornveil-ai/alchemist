"""Tests for the WS4 live-repair helpers (docs/PATH_TO_AUTONOMY.md).

The end-to-end live proof (inject a bug -> loop repairs it with the real model
-> differential tests green) runs on the box against the zlib-checksum crate.
These lock the pure, model-free helpers that drive it: brace-matched Rust
function extract/replace and failing-test -> function localization.
"""

from alchemist.autonomy.live_repair import (
    extract_rust_fn,
    replace_rust_fn,
    functions_from_failing_tests,
    _fix_byte_escapes,
)


def test_fix_byte_escapes_backslash():
    # the model's deterministic error: b'\' (unterminated) for a backslash byte
    assert _fix_byte_escapes(r"if c == b'\' { }") == r"if c == b'\\' { }"


def test_fix_byte_escapes_leaves_valid_quote():
    # a valid escaped-quote byte must be untouched
    src = r"if c == b'\'' { }"
    assert _fix_byte_escapes(src) == src


def test_fix_byte_escapes_leaves_already_correct():
    src = r"if c == b'\\' { }"
    assert _fix_byte_escapes(src) == src

_SRC = """use core::mem;

pub fn adler32_z(adler: u32, buf: &[u8], len: usize) -> u32 {
    let mut s1: u32 = adler & 0xFFFF;   // brace in comment { }
    let s2: u32 = (adler >> 16) & 0xFFFF;
    for &b in buf { s1 = s1.wrapping_add(b as u32); }
    (s2 << 16) | s1
}

fn helper<T: Clone>(x: T) -> T where T: Default { x }

pub fn other(x: u32) -> u32 { x + 1 }
"""


def test_extract_rust_fn_basic():
    got = extract_rust_fn(_SRC, "adler32_z")
    assert got is not None
    assert got.startswith("pub fn adler32_z(")
    assert got.rstrip().endswith("}")
    assert "other" not in got  # doesn't bleed into the next fn


def test_extract_handles_generics_and_where():
    got = extract_rust_fn(_SRC, "helper")
    assert got is not None
    assert got.startswith("fn helper<T: Clone>")
    assert "where T: Default" in got
    assert got.rstrip().endswith("}")


def test_extract_missing_returns_none():
    assert extract_rust_fn(_SRC, "nope") is None


def test_replace_rust_fn_preserves_siblings():
    new = replace_rust_fn(_SRC, "adler32_z", "pub fn adler32_z(a: u32) -> u32 { 42 }")
    assert new is not None
    assert "42" in new
    assert "pub fn other" in new and "fn helper" in new
    # exactly one adler32_z definition remains
    assert new.count("fn adler32_z") == 1


def test_replace_does_not_touch_braces_in_strings():
    src = 'pub fn f() -> &\'static str { "a { b } c" }\n'
    new = replace_rust_fn(src, "f", 'pub fn f() -> &\'static str { "z" }')
    assert new is not None and '"z"' in new


def test_localization_orders_by_failing_test_name():
    out = (
        "---- test_adler32_z_diff_3 stdout ----\n"
        "thread 'x' panicked at t.rs:1:1:\n"
        "assertion `left == right` failed\n"
        "  left: [1]\n right: [2]\n"
    )
    ordered = functions_from_failing_tests(out, ["crc32_z", "adler32_z", "other"])
    assert ordered[0] == "adler32_z"          # named in the failing test
    assert set(ordered) == {"crc32_z", "adler32_z", "other"}  # all retained


def test_localization_matches_base_name():
    # test named test_adler32_* should still implicate adler32_z (base match)
    out = (
        "---- test_adler32_7 stdout ----\n"
        "assertion `left == right` failed\n  left: [1]\n right: [2]\n"
    )
    ordered = functions_from_failing_tests(out, ["adler32_z", "crc32_z"])
    assert ordered[0] == "adler32_z"


def test_localization_fallback_when_no_match():
    out = "---- test_unrelated stdout ----\nassertion failed\n  left: [1]\n right: [2]\n"
    ordered = functions_from_failing_tests(out, ["a", "b"])
    assert ordered == ["a", "b"]  # original order preserved
