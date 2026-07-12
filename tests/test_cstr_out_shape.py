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
