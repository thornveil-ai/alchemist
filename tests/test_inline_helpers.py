"""Inline trivial `static inline` helpers at call sites — the fix for the
first libfixmath run (a static-inline helper split into a refusing crate broke
its caller). Must be behavior-preserving and conservative."""
from alchemist.analyzer.inline_helpers import inline_trivial_static_inlines


def test_one_arg_helper_inlined_and_removed():
    src = (
        "static inline unsigned int fix_abs(int in)"
        " { return (unsigned int)(in < 0 ? -in : in); }\n"
        "int caller(int x) { return (int)fix_abs(x - 3); }\n"
    )
    out, inlined = inline_trivial_static_inlines(src)
    assert inlined == ["fix_abs"]
    assert "fix_abs(" not in out          # call site rewritten
    assert "static inline" not in out     # definition removed
    assert "(x - 3)" in out               # arg substituted with parens


def test_two_arg_helper():
    src = (
        "static inline int add2(int a, int b) { return (a + b); }\n"
        "int use(int p, int q) { return add2(p, q * 2); }\n"
    )
    out, inlined = inline_trivial_static_inlines(src)
    assert inlined == ["add2"]
    assert "add2(" not in out
    assert "(p)" in out and "(q * 2)" in out


def test_helper_calls_helper_fixpoint():
    src = (
        "static inline int inc(int a) { return a + 1; }\n"
        "static inline int inc2(int a) { return inc(inc(a)); }\n"
        "int use(int x) { return inc2(x); }\n"
    )
    out, inlined = inline_trivial_static_inlines(src)
    assert set(inlined) == {"inc", "inc2"}
    assert "inc(" not in out and "inc2(" not in out


def test_multi_statement_inline_left_alone():
    # not a single-return body -> must NOT be touched (conservative)
    src = (
        "static inline int f(int a) { int t = a * 2; return t + 1; }\n"
        "int use(int x) { return f(x); }\n"
    )
    out, inlined = inline_trivial_static_inlines(src)
    assert inlined == []
    assert "f(x)" in out and "static inline int f" in out


def test_no_helpers_is_noop():
    src = "int plain(int a) { return a * a; }\n"
    out, inlined = inline_trivial_static_inlines(src)
    assert inlined == [] and out == src
