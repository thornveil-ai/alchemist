"""P1.15: inverse-pair roundtrip oracle for the `char* decode(char*)` shape.

base64_decode lifts to `Result<Vec<u8>, E>` (binary out), which `cstr_out`
correctly declines (the C `char*` return is NUL-lossy and random fuzz strings
aren't valid base64), so it refuses with "no verifiable test vectors". The
roundtrip oracle mints valid inputs by running the paired C ENCODER on random
plaintext and requires `decode(encode(p)) == p`. These tests cover the pure-code
sites (classifier, test emitter, proptest block); end-to-end cold verification
runs on the box against the compiled C reference."""

from __future__ import annotations

from types import SimpleNamespace as NS

import alchemist.verifier.auto_config as ac
import alchemist.verifier.proptest_gen as pg
import alchemist.implementer.test_generator as tg


def _dec():
    return NS(name="base64_decode", return_type="char *", params=[("cipher", "char *")])


def _enc():
    return NS(name="base64_encode", return_type="char *", params=[("plain", "char *")])


# --- classifier -----------------------------------------------------------

def test_decoder_with_encoder_partner_classifies():
    by_name = {"base64_decode": _dec(), "base64_encode": _enc()}
    assert ac.classify_cstr_roundtrip(_dec(), by_name) == "base64_encode"


def test_encoder_itself_does_not_classify():
    # The encoder must still flow to cstr_out — it is not a decoder.
    by_name = {"base64_decode": _dec(), "base64_encode": _enc()}
    assert ac.classify_cstr_roundtrip(_enc(), by_name) is None


def test_lone_decoder_without_encoder_refuses():
    # No paired encoder in the subject -> not a roundtrip candidate.
    assert ac.classify_cstr_roundtrip(_dec(), {"base64_decode": _dec()}) is None


def test_encoder_must_be_cstr_out_shape():
    # A partner that isn't `char* enc(char*)` disqualifies the pair.
    bad_enc = NS(name="base64_encode", return_type="int",
                 params=[("plain", "char *"), ("out", "char *")])
    by_name = {"base64_decode": _dec(), "base64_encode": bad_enc}
    assert ac.classify_cstr_roundtrip(_dec(), by_name) is None


def test_decode_encode_pair_in_the_name_table():
    # The heuristic is the shared _paired_encoder_name table.
    assert ac._paired_encoder_name("base64_decode") == "base64_encode"
    assert ac._paired_encoder_name("base64_encode") is None


# --- fill-loop test emitter ----------------------------------------------

def _vec(expected, inp='"aGk="'):
    return NS(inputs={"cipher": inp}, expected_output=expected,
              tolerance="roundtrip", description="rt", source="s")


def test_emit_roundtrip_vec_return_uses_unwrap_and_slice():
    out = tg._emit_roundtrip_test("base64_decode", _vec('b"hi"'), 0,
                                  "Result<Vec<u8>, Base64Error>")
    assert ".unwrap()" in out          # Result -> unwrap (no PartialEq on E)
    assert ".as_slice()" in out
    assert '&b"hi"[..]' in out


def test_emit_roundtrip_plain_vec_return_no_unwrap():
    out = tg._emit_roundtrip_test("foo_decode", _vec('b"hi"'), 0, "Vec<u8>")
    assert ".unwrap()" not in out
    assert ".as_slice()" in out


def test_emit_roundtrip_text_return_compares_str():
    out = tg._emit_roundtrip_test("foo_decode", _vec('"hi"'), 1, "String")
    assert ".as_str()" in out
    assert '"hi"' in out


def test_roundtrip_dispatch_is_wired():
    # _emit_spec_test must route tolerance="roundtrip" to the roundtrip emitter.
    out = tg._emit_spec_test("base64_decode", _vec('b"hi"'), 0,
                             return_type="Result<Vec<u8>, E>", alg=None)
    assert "roundtrip" in out and ".unwrap()" in out


# --- differential proptest block -----------------------------------------

def test_cstr_roundtrip_is_a_valid_category():
    assert "cstr_roundtrip" in pg.VALID_CATEGORIES


def test_proptest_block_mints_via_encoder_and_asserts_identity():
    h = pg.AlgorithmHarness(
        algorithm="base64_decode", category="cstr_roundtrip",
        rust_call="rust_base64_decode(&input)", c_call="",
        encoder_c_call="c_base64_decode_enc(&pt)",
        input_strategy="prop::collection::vec(1u8..=255u8, 0..48)", cases=2000)
    block = pg._proptest_block(h)
    assert "c_base64_decode_enc(&pt)" in block          # mint via C encoder
    assert "rust_base64_decode(&input)" in block        # Rust decoder
    assert "prop_assert_eq!(rust_out.as_slice(), pt.as_slice())" in block
    assert "unverifiable" not in block                  # not the fail-closed stub
