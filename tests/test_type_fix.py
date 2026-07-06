"""Mechanical integer-width coercion — parsing + rewrites (no rustc)."""

from alchemist.autonomy.type_fix import parse_type_errors, apply_type_fix

E0277 = """\
error[E0277]: no implementation for `u8 ^= u32`
   --> src/lib.rs:22:9
    |
22  |         c ^= s[k];
"""

E0308 = """\
error[E0308]: mismatched types
   --> src/lib.rs:40:20
    |
40  |         state[i] = word;
    |                    ^^^^ expected `u8`, found `u32`
"""


def test_parse_compound_assign():
    assert parse_type_errors(E0277) == [("compound", 22, "u8")]


def test_parse_e0308_int_mismatch():
    assert parse_type_errors(E0308) == [("assign", 40, "u8")]


def test_fix_compound_assign():
    src = "fn f() {\n    c ^= s[k];\n}"
    out = apply_type_fix(src, 2, "u8")
    assert out.split("\n")[1].strip() == "c ^= (s[k]) as u8;"


def test_fix_plain_assign():
    src = "fn f() {\n    state[i] = word;\n}"
    out = apply_type_fix(src, 2, "u8")
    assert out.split("\n")[1].strip() == "state[i] = (word) as u8;"


def test_no_double_cast():
    # already cast -> don't touch (would loop forever)
    src = "fn f() {\n    c ^= (s[k]) as u8;\n}"
    assert apply_type_fix(src, 2, "u8") is None


def test_skips_let_with_type_annotation():
    src = "fn f() {\n    let x: u32 = 0;\n}"
    assert apply_type_fix(src, 2, "u8") is None


def test_non_int_expected_ignored():
    # E0308 with a struct type is not our job
    out = "error[E0308]: mismatched types\n   --> src/lib.rs:5:1\n   expected `Foo`, found `Bar`\n"
    assert parse_type_errors(out) == []
