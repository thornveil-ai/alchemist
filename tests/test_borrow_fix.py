"""Mechanical borrow-restructuring — error parsing + the two rewrites (no rustc).

End-to-end (fix a real model-produced borrow conflict) runs on the box.
"""

from alchemist.autonomy.borrow_fix import (
    parse_borrow_errors, apply_borrow_fix,
)

E0502_OUTPUT = """\
error[E0502]: cannot borrow `*ctx` as mutable because it is also borrowed as immutable
   --> src/lib.rs:120:9
    |
120 |         sha256_transform(ctx, &ctx.data);
    |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
"""


def test_parse_borrow_errors():
    errs = parse_borrow_errors(E0502_OUTPUT)
    assert errs == [("E0502", 120, "ctx")]


def test_pattern_a_hoists_field_borrow():
    src = "\n".join(["fn f() {", "    sha256_transform(ctx, &ctx.data);", "}"])
    out = apply_borrow_fix(src, 2, "ctx", 0)
    assert out is not None
    lines = out.split("\n")
    assert lines[1].strip() == "let __brw0 = ctx.data;"
    assert lines[2].strip() == "sha256_transform(ctx, &__brw0);"


def test_pattern_a_with_index():
    src = "fn f() {\n    transform(s, &s.window[i]);\n}"
    out = apply_borrow_fix(src, 2, "s", 3)
    assert "let __brw3 = s.window[i];" in out
    assert "transform(s, &__brw3);" in out


def test_pattern_b_hoists_self_assign_rhs():
    src = "fn f() {\n    strm.state.match_length = longest_match(&mut strm.state, hash_head);\n}"
    out = apply_borrow_fix(src, 2, "strm", 1)
    lines = out.split("\n")
    assert lines[1].strip() == "let __brw1 = longest_match(&mut strm.state, hash_head);"
    assert lines[2].strip() == "strm.state.match_length = __brw1;"


def test_pattern_b_compound_assign():
    src = "fn f() {\n    s.opt_len += cost(&mut s, n);\n}"
    out = apply_borrow_fix(src, 2, "s", 0)
    assert "let __brw0 = cost(&mut s, n);" in out
    assert "s.opt_len += __brw0;" in out


def test_no_pattern_returns_none():
    src = "fn f() {\n    let z = a + b;\n}"
    assert apply_borrow_fix(src, 2, "ctx", 0) is None
