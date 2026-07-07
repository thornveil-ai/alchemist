"""Decomposition — statement-macro extraction + bottom-up sub-unit plan."""

from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.decompose import extract_statement_macro, decomposition_plan


def test_extract_blowfish_f_macro_as_verifiable_unit():
    body = ("t = k->s[0][(x)>>24]; t += k->s[1][((x)>>16)&0xff]; "
            "t ^= k->s[2][((x)>>8)&0xff]; t += k->s[3][(x)&0xff];")
    spec = extract_statement_macro("blowfish_f", "x, t", body)
    assert spec["output"] == "t"                 # the assigned param is the output
    assert spec["inputs"] == ["x"]               # the rest are inputs
    assert spec["ctx"] == ["k"]                  # reached through k->
    assert spec["is_verifiable"] is True         # input + output -> a pure sub-fn
    assert "blowfish_f(k: &Ctx, x: u32) -> u32" in spec["rust_sig"]


def test_extract_handles_compound_assign_output():
    spec = extract_statement_macro("mix", "a, acc", "acc ^= a; acc <<= 3;")
    assert spec["output"] == "acc" and spec["inputs"] == ["a"]


def test_decomposition_plan_pieces_before_composer():
    src = ("unsigned round(unsigned y) { return y + 1; }\n"
           "unsigned enc(unsigned x) { unsigned t; F(x, t); return round(t); }\n")
    funcs = discover_functions(src)
    plan = decomposition_plan(funcs["enc"], funcs, {"F": "t = ...;"})
    assert plan.index("F") < plan.index("enc")       # macro piece first
    assert plan.index("round") < plan.index("enc")   # callee piece first
    assert plan[-1] == "enc"                          # composer last
