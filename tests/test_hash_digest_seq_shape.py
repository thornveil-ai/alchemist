"""P1.17: digest-sequence oracle for the CONTEXT-HASH class (SHA-256/SHA-1/MD5/HMAC).

A decomposed context hash is `init(ctx)` + `update(ctx, data, len)` +
`final(ctx, out_digest)` over a MULTI-FIELD context struct, with `final` writing
an N-byte digest into an out-buffer. The existing `hash_seq` only covered a
single-scalar state with a scalar-returning `final` (FNV-shaped), so SHA-256
hit "no test vectors" for all 4 functions. These tests cover the pure-code
classification/parsing; the vector correctness (digests match hashlib.sha256)
is cross-checked on the box against the compiled C reference."""

from __future__ import annotations

from types import SimpleNamespace as NS

import alchemist.verifier.auto_config as ac
from alchemist.verifier.struct_lift import Field


def _sha256_sigs():
    return {
        "sha256_init": NS(name="sha256_init", return_type="void",
                          params=[("ctx", "SHA256_CTX *")]),
        "sha256_update": NS(name="sha256_update", return_type="void",
                            params=[("ctx", "SHA256_CTX *"),
                                    ("arg1", "const BYTE data[]"), ("len", "size_t")]),
        "sha256_final": NS(name="sha256_final", return_type="void",
                           params=[("ctx", "SHA256_CTX *"), ("arg1", "BYTE hash[]")]),
        "sha256_transform": NS(name="sha256_transform", return_type="void",
                               params=[("ctx", "SHA256_CTX *"), ("arg1", "const BYTE data[]")]),
    }


def _sha256_struct():
    return {"SHA256_CTX": [
        Field("data", "unsigned char", 64, False),
        Field("datalen", "unsigned int", None, False),
        Field("bitlen", "unsigned long long", None, False),
        Field("state", "unsigned int", 8, False),
    ]}


def _specs():
    # only `final`'s out-param lift carries the digest length
    final = NS(name="sha256_final",
               inputs=[NS(name="ctx", rust_type="&mut Sha256Context"),
                       NS(name="hash", rust_type="&mut [u8; 32]")])
    init = NS(name="sha256_init", inputs=[NS(name="ctx", rust_type="&mut Sha256Context")])
    return [NS(algorithms=[init, final])]


# --- byte-buffer param matchers (raw C array-declarator forms) ---

def test_const_byte_buf_matches_array_and_pointer_forms():
    assert ac._is_const_byte_buf("const BYTE data[]")
    assert ac._is_const_byte_buf("const unsigned char *")
    assert not ac._is_const_byte_buf("BYTE hash[]")       # not const
    assert not ac._is_const_byte_buf("size_t")


def test_mut_byte_buf_matches_nonconst_only():
    assert ac._is_mut_byte_buf("BYTE hash[]")
    assert ac._is_mut_byte_buf("unsigned char *")
    assert not ac._is_mut_byte_buf("const BYTE data[]")   # const -> not a mut out-buf


def test_digest_len_read_from_final_lift():
    assert ac._digest_len_from_specs(_specs(), "sha256_final") == 32
    assert ac._digest_len_from_specs(_specs(), "sha256_init") is None


# --- classifier ---

def test_sha256_classifies_as_digest_sequence():
    g = ac.classify_hash_digest_sequence(_sha256_sigs(), _sha256_struct(), _specs())
    assert g is not None
    assert g["init"][0] == "sha256_init"
    assert g["update"][0] == "sha256_update"
    assert g["final"][0] == "sha256_final"
    assert g["transform"][0] == "sha256_transform"
    assert g["digest_len"] == 32
    assert g["rust"] == "Sha256Context"


def test_single_scalar_state_is_left_to_hash_seq():
    # An FNV-style single-scalar state must NOT be claimed here (that's hash_seq).
    sigs = {
        "fnv_init": NS(name="fnv_init", return_type="void", params=[("s", "FnvState *")]),
        "fnv_update": NS(name="fnv_update", return_type="void",
                         params=[("s", "FnvState *"), ("d", "const BYTE data[]"), ("n", "size_t")]),
        "fnv_final": NS(name="fnv_final", return_type="void",
                        params=[("s", "FnvState *"), ("o", "BYTE out[]")]),
    }
    structs = {"FnvState": [Field("hash", "unsigned int", None, False)]}
    assert ac.classify_hash_digest_sequence(sigs, structs, _specs()) is None


def test_missing_final_is_not_a_sequence():
    sigs = _sha256_sigs()
    del sigs["sha256_final"]
    assert ac.classify_hash_digest_sequence(sigs, _sha256_struct(), _specs()) is None
