"""L2 lever: seeded hash-to-output-buffer shape (MurmurHash family).

`void f(const void* key, int len, uint32_t seed, void* out)` — the C writes a
fixed-size digest through an opaque out pointer and returns void. This shape is
invisible to the checksum (needs a scalar return) and digest (needs int return +
outlen) classifiers, so without this lever the whole void*-out hash class is
unverifiable. The Rust target returns the digest as `Vec<u8>`.
"""
from alchemist.verifier.auto_config import (
    classify_hash_out_shape, _hash_out_len_for, HashOutShape,
)


def _sig(name, ret, params):
    from alchemist.verifier.auto_ffi import CSignature
    return CSignature(name=name, return_type=ret, params=params)


def test_murmur_x86_32_classifies_with_4byte_out():
    s = _sig("MurmurHash3_x86_32", "void",
             [("key", "const void *"), ("len", "int"),
              ("seed", "uint32_t"), ("out", "void *")])
    d = classify_hash_out_shape(s)
    assert d is not None
    assert (d.in_idx, d.inlen_idx, d.seed_idx, d.out_idx, d.out_len) == (0, 1, 2, 3, 4)


def test_murmur_128_variants_out_len_16():
    for name in ("MurmurHash3_x86_128", "MurmurHash3_x64_128"):
        s = _sig(name, "void",
                 [("key", "const void *"), ("len", "int"),
                  ("seed", "uint32_t"), ("out", "void *")])
        d = classify_hash_out_shape(s)
        assert d is not None and d.out_len == 16


def test_out_len_from_trailing_bitwidth():
    assert _hash_out_len_for("MurmurHash3_x86_32") == 4
    assert _hash_out_len_for("MurmurHash3_x64_128") == 16
    assert _hash_out_len_for("hash256") == 32


def test_non_void_return_is_not_hash_out():
    # A scalar-returning hash is a checksum, not this shape.
    s = _sig("h", "uint32_t",
             [("key", "const void *"), ("len", "int"),
              ("seed", "uint32_t"), ("out", "void *")])
    assert classify_hash_out_shape(s) is None


def test_byte_ptrs_also_accepted():
    # Not every such hash uses void*; unsigned char* out must classify too.
    s = _sig("h32", "void",
             [("key", "const unsigned char *"), ("len", "size_t"),
              ("seed", "uint32_t"), ("out", "unsigned char *")])
    d = classify_hash_out_shape(s)
    assert d is not None and d.out_len == 4
