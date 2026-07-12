"""P0.8a — the cstr_out oracle shape: `char* f(char*)` (NUL-string in, malloc'd
string out), e.g. base64_encode. Found via the refusal ledger (base64 → 100%
refusal, "no test vectors"): such text-transform fns are FFI-verifiable but had
no shape, so they were skipped and refused. This adds the text-out case.
"""

from __future__ import annotations

from alchemist.verifier.auto_config import (
    classify_cstr_out,
    fuzz_cstr_out_vectors,
    _rust_bytes_lit,
)


class _Sig:
    def __init__(self, name, ret, params):
        self.name = name
        self.return_type = ret
        self.params = params


def test_classify_cstr_out():
    assert classify_cstr_out(_Sig("base64_encode", "char *", [("plain", "char *")])) == "cstr_out"
    assert classify_cstr_out(_Sig("f", "const char *", [("x", "unsigned char *")])) == "cstr_out"
    # Not a single char* param, or non-string return → not this shape.
    assert classify_cstr_out(_Sig("f", "char *", [("a", "char *"), ("b", "char *")])) is None
    assert classify_cstr_out(_Sig("f", "int", [("x", "char *")])) is None
    assert classify_cstr_out(_Sig("f", "char *", [("x", "int")])) is None


def test_rust_bytes_lit():
    assert _rust_bytes_lit(b"hello") == 'b"hello"'
    assert _rust_bytes_lit(bytes([1, 2])) == 'b"\\x01\\x02"'
    # quote and backslash are escaped
    assert _rust_bytes_lit(b'a"b') == 'b"a\\"b"'


class _P:
    def __init__(self, name, rust_type):
        self.name = name
        self.rust_type = rust_type


class _Alg:
    def __init__(self, ret, inputs):
        self.return_type = ret
        self.inputs = inputs
        self.name = "base64_encode"


def test_fuzzer_declines_binary_out_lift():
    """base64_decode lifts to Result<Vec<u8>> — the C char* return is NUL-lossy for
    binary output, so the fuzzer must decline (honest refusal, not a lossy oracle)."""
    sig = _Sig("base64_decode", "char *", [("cipher", "char *")])
    alg = _Alg("Result<Vec<u8>, Base64Error>", [_P("cipher", "&str")])
    assert fuzz_cstr_out_vectors(dll=None, alg=alg, sig=sig) == []


def test_fuzzer_declines_non_string_return():
    sig = _Sig("f", "char *", [("x", "char *")])
    alg = _Alg("Vec<u8>", [_P("x", "&[u8]")])
    assert fuzz_cstr_out_vectors(dll=None, alg=alg, sig=sig) == []


# ---- P0.9 follow-up: cstr_out must also reach the FINAL differential gate. ----
# The leaf benchmark (P0.11) surfaced the gap: to_upper/rot13/hex_encode verified
# byte-exact in the TDD loop yet the whole-workspace verify refused with
# "no differential config provided" — because build_diff_config, the runtime
# differential harness renderer (proptest_gen), and the FFI adapter (adapter_gen)
# had no cstr_out branch. These three tests lock the wiring in.

def test_proptest_block_for_cstr_out():
    from alchemist.verifier.proptest_gen import AlgorithmHarness, emit_differential_test
    h = AlgorithmHarness(
        algorithm="to_upper",
        category="cstr_out",
        rust_call="rust_to_upper(&input)",
        c_call="c_to_upper(&input)",
        input_strategy=r'"[ -~]{0,48}"',
        cases=4000,
    )
    src = emit_differential_test([h], module_doc="cstr differential")
    assert "fn to_upper_matches_c_reference(input in \"[ -~]{0,48}\")" in src
    assert "let rust_out = rust_to_upper(&input);" in src
    assert "let c_out = c_to_upper(&input);" in src
    assert "prop_assert_eq!(rust_out, c_out)" in src
    # printable range spans lowercase so a case-changer is actually exercised
    assert "a" not in src or "[ -~]" in src  # sanity: the range covers 'a'..'z'


def test_adapter_lib_for_cstr_out(tmp_path):
    from alchemist.verifier.adapter_gen import emit_adapter_lib, plan_adapters
    from alchemist.verifier.proptest_gen import AlgorithmHarness
    from alchemist.verifier.auto_ffi import CSignature

    pkg = tmp_path / "text-xform"
    (pkg / "src").mkdir(parents=True)
    (pkg / "Cargo.toml").write_text(
        '[package]\nname = "text-xform"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8")
    (pkg / "src" / "lib.rs").write_text(
        "#![forbid(unsafe_code)]\n"
        "pub fn to_upper(input: &str) -> String { input.to_uppercase() }\n",
        encoding="utf-8")

    h = AlgorithmHarness(
        algorithm="to_upper", category="cstr_out",
        rust_call="rust_to_upper(&input)", c_call="c_to_upper(&input)",
    )
    sig = CSignature(name="to_upper", return_type="char *", params=[("s", "char *")])
    plan = plan_adapters([h], rust_workspace=tmp_path,
                         ffi_crate_name="c_text_ref", c_signatures=[sig])
    lib = emit_adapter_lib(plan, ffi_crate_name="c_text_ref")
    # Rust side calls the model's fn; C side reads the returned heap string back.
    assert "pub fn rust_to_upper(input: &str) -> String" in lib
    assert "pub fn c_to_upper(input: &str) -> String" in lib
    assert "c_text_ref::to_upper(cin.as_ptr() as _)" in lib
    assert "CStr::from_ptr(rp as *const _)" in lib
    assert "CString::new(input)" in lib


def test_build_diff_config_emits_cstr_out_harness(tmp_path):
    """The real gap: without a build_diff_config branch the final gate got no
    harness for a char* f(char*) fn and refused a verified translation."""
    from alchemist.verifier.auto_config import build_diff_config

    (tmp_path / "to_upper.c").write_text(
        "#include <stdlib.h>\n#include <string.h>\n"
        "char *to_upper(char *s) {\n"
        "    size_t n = strlen(s);\n"
        "    char *out = (char *)malloc(n + 1);\n"
        "    for (size_t i = 0; i < n; i++) { char c = s[i];"
        " out[i] = (c >= 'a' && c <= 'z') ? (char)(c - 32) : c; }\n"
        "    out[n] = 0; return out;\n}\n",
        encoding="utf-8")

    alg = _Alg("String", [_P("s", "&str")])
    alg.name = "to_upper"
    alg.category = "utility"
    module = type("Mod", (), {"algorithms": [alg]})()

    cfg = build_diff_config(tmp_path, [module])
    assert cfg is not None, "cstr_out fn must yield a differential config, not None"
    cats = [h.category for h in cfg.harnesses]
    assert "cstr_out" in cats, f"expected a cstr_out harness, got {cats}"
    h = next(h for h in cfg.harnesses if h.category == "cstr_out")
    assert h.rust_call == "rust_to_upper(&input)"
    assert h.c_call == "c_to_upper(&input)"


def test_cipher_labelled_cstr_out_still_configured(tmp_path):
    """rot13 IS a substitution cipher, so the extractor labels its algorithm
    'cipher'. The cipher/compression early-skip must NOT starve a clean
    `char* f(char*)` shape — else a byte-exact-verified rot13 refuses at the
    final gate with 'no differential config provided' (the real P0.11 miss)."""
    from alchemist.verifier.auto_config import build_diff_config

    (tmp_path / "rot13.c").write_text(
        "#include <stdlib.h>\n#include <string.h>\n"
        "char *rot13(char *s) {\n"
        "    size_t n = strlen(s);\n"
        "    char *out = (char *)malloc(n + 1);\n"
        "    for (size_t i = 0; i < n; i++) { char c = s[i];"
        " if (c >= 'a' && c <= 'z') out[i] = (char)('a' + (c - 'a' + 13) % 26);"
        " else if (c >= 'A' && c <= 'Z') out[i] = (char)('A' + (c - 'A' + 13) % 26);"
        " else out[i] = c; }\n"
        "    out[n] = 0; return out;\n}\n",
        encoding="utf-8")

    alg = _Alg("String", [_P("s", "&str")])
    alg.name = "rot13"
    alg.category = "cipher"  # the mislabel that used to drop it
    module = type("Mod", (), {"algorithms": [alg]})()

    cfg = build_diff_config(tmp_path, [module])
    assert cfg is not None, "cipher-labelled cstr_out must still get a config"
    assert any(h.category == "cstr_out" for h in cfg.harnesses)
