"""Regression: the structural-decomposition equivalence gate supports the scalar
shape — it accepts a behavior-preserving split of an all-scalar function and
rejects a divergent one. This is what lets a hard scalar function (fix16_div) be
decomposed into individually-verifiable helpers."""
from alchemist.implementer.structural_decomp import (
    HelperFn,
    Decomposition,
    classify_scalar_proto,
    verify_c_decomposition_equivalent,
)


def test_classify_scalar_proto():
    assert classify_scalar_proto("fix16_t fix16_div(fix16_t a, fix16_t b)") is not None
    assert classify_scalar_proto("int isqrt(unsigned int x)") is not None
    # pointers / buffers are NOT scalar
    assert classify_scalar_proto("int f(const char* in, int n, char* out, int c)") is None
    assert classify_scalar_proto("void f(void)") is None


def test_scalar_gate_accepts_correct_split_rejects_buggy():
    orig = "int f(int a, int b)\n{\n    return a * 2 + b;\n}"
    helper = HelperFn(name="f__dbl", signature="int f__dbl(int a)",
                      source="int f__dbl(int a){ return a*2; }")
    good = Decomposition(original_name="f", helpers=[helper],
                         driver_source="int f(int a, int b){ return f__dbl(a) + b; }")
    bad = Decomposition(original_name="f", helpers=[helper],
                        driver_source="int f(int a, int b){ return f__dbl(a) - b; }")
    ok_good, _ = verify_c_decomposition_equivalent(
        original_c=orig, decomposition=good, fn_name="f", shape="scalar")
    ok_bad, _ = verify_c_decomposition_equivalent(
        original_c=orig, decomposition=bad, fn_name="f", shape="scalar")
    assert ok_good is True
    assert ok_bad is False


def test_scalar_gate_divisor_safe():
    # A function that divides: the gate must keep args nonzero so a
    # guard-preserving split isn't SIGFPE'd. Identity split of a guarded div.
    orig = ("int g(int a, int b)\n{\n    if (b == 0) return -1;\n"
            "    return a / b;\n}")
    helper = HelperFn(name="g__do", signature="int g__do(int a, int b)",
                      source="int g__do(int a, int b){ return a / b; }")
    good = Decomposition(original_name="g", helpers=[helper],
                         driver_source="int g(int a, int b){ if (b==0) return -1; return g__do(a,b); }")
    ok, rep = verify_c_decomposition_equivalent(
        original_c=orig, decomposition=good, fn_name="g", shape="scalar")
    assert ok is True, rep
