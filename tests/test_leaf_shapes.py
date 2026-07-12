"""P0.8 — two leaf shapes the false-refusal sweep closed:

  iarray_reduce : `<scalar> f(const T* a, int n)`  (sum_array, min/max/dot)
  cstr_scalar   : `<scalar> f(const char* s, ...)` (count_char, strlen, atoi)

Both were honest coverage gaps (no oracle -> "no differential config" -> refuse)
surfaced by the leaf benchmark's planted "uncovered" subjects. These lock the
full wiring (classify -> build_diff_config harness -> proptest block -> FFI
adapter) so the shapes stay differentially verifiable, not refused.
"""

from __future__ import annotations

from alchemist.verifier.auto_config import (
    classify_iarray_reduce,
    classify_cstr_scalar,
    build_diff_config,
)


class _Sig:
    def __init__(self, name, ret, params):
        self.name = name
        self.return_type = ret
        self.params = params


class _P:
    def __init__(self, name, rust_type):
        self.name = name
        self.rust_type = rust_type


class _Alg:
    def __init__(self, name, ret, inputs, category=""):
        self.name = name
        self.return_type = ret
        self.inputs = inputs
        self.category = category


# ---------------- classifiers ----------------

def test_classify_iarray_reduce():
    assert classify_iarray_reduce(
        _Sig("sum_array", "long", [("a", "const int *"), ("n", "int")])
    ) == {"elem_c": "int", "elem_rust": "i32", "ret_rust": "i64"}
    # byte-element pointers belong to the checksum/digest shapes, not this one
    assert classify_iarray_reduce(
        _Sig("crc", "unsigned", [("b", "const unsigned char *"), ("n", "int")])) is None
    # a non-scalar (pointer) return is not a reduction
    assert classify_iarray_reduce(
        _Sig("f", "char *", [("a", "const int *"), ("n", "int")])) is None
    # need exactly (array, len)
    assert classify_iarray_reduce(_Sig("f", "int", [("a", "const int *")])) is None


def test_classify_cstr_scalar():
    assert classify_cstr_scalar(
        _Sig("count_char", "int", [("s", "const char *"), ("c", "char")])) == ["char"]
    assert classify_cstr_scalar(_Sig("strlen", "int", [("s", "const char *")])) == []
    # char* return is cstr_out territory, not this
    assert classify_cstr_scalar(_Sig("f", "char *", [("s", "char *")])) is None
    # a non-scalar extra arg disqualifies it
    assert classify_cstr_scalar(
        _Sig("f", "int", [("s", "char *"), ("p", "int *")])) is None


# ---------------- build_diff_config emits a harness (the gate no longer refuses) ----------------

def test_build_diff_config_iarray_reduce(tmp_path):
    (tmp_path / "sum_array.c").write_text(
        "long sum_array(const int *a, int n) {\n"
        "    long s = 0; for (int i = 0; i < n; i++) s += a[i]; return s;\n}\n",
        encoding="utf-8")
    alg = _Alg("sum_array", "i64", [_P("a", "&[i32]")])
    module = type("Mod", (), {"algorithms": [alg]})()
    cfg = build_diff_config(tmp_path, [module])
    assert cfg is not None
    h = next(h for h in cfg.harnesses if h.category == "iarray_reduce")
    assert h.rust_call == "rust_sum_array(&input)"
    assert h.state_rust == "i32"
    assert "..=" in (h.input_strategy or "")  # bounded element range (no overflow UB)


def test_build_diff_config_cstr_scalar(tmp_path):
    (tmp_path / "count_char.c").write_text(
        "int count_char(const char *s, char c) {\n"
        "    int n = 0; while (*s) { if (*s == c) n++; s++; } return n;\n}\n",
        encoding="utf-8")
    alg = _Alg("count_char", "i32", [_P("s", "&str"), _P("c", "i8")])
    module = type("Mod", (), {"algorithms": [alg]})()
    cfg = build_diff_config(tmp_path, [module])
    assert cfg is not None
    h = next(h for h in cfg.harnesses if h.category == "cstr_scalar")
    # call passes the string plus the one extra scalar, positionally
    assert h.rust_call == "rust_count_char(&s, a0)"
    assert h.c_call == "c_count_char(&s, a0)"
    assert h.scalar_arg_types == ["i8"]


def test_build_diff_config_cstr_scalar_coerces_stale_char(tmp_path):
    """The verify stage can hold a PRE-normalization spec where the `char` value-arg
    is still Rust `char`. build_diff_config must coerce it to i8 so the proptest scalar
    type matches the wrappers (which adapter_gen derives from the normalized model)."""
    (tmp_path / "count_char.c").write_text(
        "int count_char(const char *s, char c) { int n=0; while(*s){ if(*s==c) n++; s++; } return n; }\n",
        encoding="utf-8")
    # note: c is STILL "char" here (stale spec), not yet normalized to i8
    alg = _Alg("count_char", "i32", [_P("s", "&str"), _P("c", "char")])
    module = type("Mod", (), {"algorithms": [alg]})()
    cfg = build_diff_config(tmp_path, [module])
    h = next(h for h in cfg.harnesses if h.category == "cstr_scalar")
    assert h.scalar_arg_types == ["i8"], "stale `char` must be coerced to i8"


def test_normalize_char_scalar_param(tmp_path):
    """A C `char` value-arg mis-lifts to Rust `char`; the normalizer re-lifts it to i8
    (or u8 for `unsigned char`) so the byte oracle can round-trip it."""
    from alchemist.verifier.auto_config import normalize_char_scalar_params
    (tmp_path / "count_char.c").write_text(
        "int count_char(const char *s, char c) { int n=0; while(*s){ if(*s==c) n++; s++; } return n; }\n",
        encoding="utf-8")
    s = _P("s", "&str")
    c = _P("c", "char")               # the mis-lift
    alg = _Alg("count_char", "usize", [s, c])
    module = type("Mod", (), {"algorithms": [alg]})()
    n = normalize_char_scalar_params(tmp_path, [module])
    assert n == 1
    assert c.rust_type == "i8"         # re-lifted
    assert s.rust_type == "&str"       # the string pointer is untouched


def test_checksum_still_wins_over_cstr_scalar(tmp_path):
    """A `(const char*, int-len)` is a byte buffer — checksum must claim it, not
    cstr_scalar (which is the fallback for string+char / bare-string leftovers)."""
    (tmp_path / "sum8.c").write_text(
        "unsigned char sum8(const unsigned char *data, int len) {\n"
        "    unsigned char s = 0; for (int i=0;i<len;i++) s=(unsigned char)(s+data[i]); return s;\n}\n",
        encoding="utf-8")
    alg = _Alg("sum8", "u8", [_P("data", "&[u8]")])
    module = type("Mod", (), {"algorithms": [alg]})()
    cfg = build_diff_config(tmp_path, [module])
    assert cfg is not None
    cats = {h.category for h in cfg.harnesses}
    assert "checksum" in cats and "cstr_scalar" not in cats


# ---------------- proptest + adapter rendering ----------------

def test_proptest_blocks_render():
    from alchemist.verifier.proptest_gen import AlgorithmHarness, emit_differential_test
    ir = AlgorithmHarness(
        algorithm="sum_array", category="iarray_reduce",
        rust_call="rust_sum_array(&input)", c_call="c_sum_array(&input)",
        state_rust="i32", input_strategy="prop::collection::vec(-1i32..=1i32, 0..64)")
    cs = AlgorithmHarness(
        algorithm="count_char", category="cstr_scalar",
        rust_call="rust_count_char(&s, a0)", c_call="c_count_char(&s, a0)",
        scalar_arg_types=["i8"])
    src = emit_differential_test([ir, cs], module_doc="leaf shapes")
    assert "fn sum_array_matches_c_reference(input in" in src
    assert "fn count_char_matches_c_reference((s, a0) in" in src
    assert 'any::<i8>()' in src and '"[ -~]{0,48}"' in src


def _write_crate(root, pkg, lib_rs):
    d = root / pkg
    (d / "src").mkdir(parents=True)
    (d / "Cargo.toml").write_text(
        f'[package]\nname = "{pkg}"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8")
    (d / "src" / "lib.rs").write_text(lib_rs, encoding="utf-8")


def test_adapter_iarray_reduce(tmp_path):
    from alchemist.verifier.adapter_gen import emit_adapter_lib, plan_adapters
    from alchemist.verifier.proptest_gen import AlgorithmHarness
    from alchemist.verifier.auto_ffi import CSignature
    _write_crate(tmp_path, "arr", "#![forbid(unsafe_code)]\n"
                 "pub fn sum_array(a: &[i32]) -> i64 { a.iter().map(|&x| x as i64).sum() }\n")
    h = AlgorithmHarness(algorithm="sum_array", category="iarray_reduce",
                         rust_call="rust_sum_array(&input)", c_call="c_sum_array(&input)",
                         state_rust="i32")
    sig = CSignature(name="sum_array", return_type="long",
                     params=[("a", "const int *"), ("n", "int")])
    plan = plan_adapters([h], rust_workspace=tmp_path, ffi_crate_name="c_arr_ref",
                         c_signatures=[sig])
    lib = emit_adapter_lib(plan, ffi_crate_name="c_arr_ref")
    assert "pub fn rust_sum_array(input: &[i32]) -> i64" in lib
    assert "pub fn c_sum_array(input: &[i32]) -> i64" in lib
    assert "c_arr_ref::sum_array(input.as_ptr() as _, input.len() as _)" in lib


def test_adapter_cstr_scalar(tmp_path):
    from alchemist.verifier.adapter_gen import emit_adapter_lib, plan_adapters
    from alchemist.verifier.proptest_gen import AlgorithmHarness
    from alchemist.verifier.auto_ffi import CSignature
    _write_crate(tmp_path, "cc", "#![forbid(unsafe_code)]\n"
                 "pub fn count_char(s: &str, c: i8) -> i32 "
                 "{ s.bytes().filter(|&b| b as i8 == c).count() as i32 }\n")
    h = AlgorithmHarness(algorithm="count_char", category="cstr_scalar",
                         rust_call="rust_count_char(&s, a0)", c_call="c_count_char(&s, a0)",
                         scalar_arg_types=["i8"])
    sig = CSignature(name="count_char", return_type="int",
                     params=[("s", "const char *"), ("c", "char")])
    plan = plan_adapters([h], rust_workspace=tmp_path, ffi_crate_name="c_cc_ref",
                         c_signatures=[sig])
    lib = emit_adapter_lib(plan, ffi_crate_name="c_cc_ref")
    assert "pub fn rust_count_char(s: &str, a0: i8) -> i32" in lib
    assert "pub fn c_count_char(s: &str, a0: i8) -> i32" in lib
    assert "CString::new(s)" in lib
    assert "c_cc_ref::count_char(cs.as_ptr() as _, a0 as _)" in lib
