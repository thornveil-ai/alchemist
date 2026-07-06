"""Auto-oracle: signature classification + Rust signature + C call generation.

The hand-written apcrc setup classified each param by eye (buffer / len / seed);
this derives the same mapping from the signature alone.
"""

from alchemist.autonomy.onboard import CFunc
from alchemist.autonomy.oracle_gen import (
    classify_signature, rust_signature, c_call_args, generate_c_harness,
)


def _fn(name, ret, params):
    return CFunc(name=name, ret=ret, params=params)


def test_buffer_len():
    s = classify_signature(_fn("crc_crc8", "uint8_t", "const uint8_t *p, uint8_t len"))
    roles = [p.role for p in s.params]
    assert roles == ["buffer", "len"]
    assert rust_signature(s) == "pub fn crc_crc8(data: &[u8]) -> u8"
    assert c_call_args(s) == "in, l"


def test_seed_buffer_len():
    s = classify_signature(_fn("crc_crc32", "uint32_t", "uint32_t crc, const uint8_t *buf, uint32_t size"))
    assert [p.role for p in s.params] == ["scalar", "buffer", "len"]
    assert rust_signature(s) == "pub fn crc_crc32(crc: u32, data: &[u8]) -> u32"
    assert c_call_args(s) == "0, in, l"


def test_buffer_len_seed():
    s = classify_signature(_fn("crc16_ccitt", "uint16_t", "const uint8_t *buf, uint32_t len, uint16_t crc"))
    assert [p.role for p in s.params] == ["buffer", "len", "scalar"]
    assert rust_signature(s) == "pub fn crc16_ccitt(data: &[u8], crc: u16) -> u16"
    assert c_call_args(s) == "in, l, 0"


def test_void_pointer_buffer():
    s = classify_signature(_fn("crc8_dvb_s2_update", "uint8_t", "uint8_t crc, const void *data, uint32_t length"))
    assert [p.role for p in s.params] == ["scalar", "buffer", "len"]
    assert s.supported


def test_out_pointer_is_unsupported():
    # hash_fnv_1a(len, buf, uint64_t *hash) — the mutable out-pointer isn't a
    # clean buffer; classify as unknown rather than guess.
    s = classify_signature(_fn("hash_fnv_1a", "void", "uint32_t len, const uint8_t *buf, uint64_t *hash"))
    assert not s.supported
    assert any(p.role == "unknown" for p in s.params)


def test_default_arg_stripped():
    s = classify_signature(_fn("crc8_generic", "uint8_t",
                               "const uint8_t *buf, const uint16_t buf_len, const uint8_t polynomial, uint8_t initial_value=0"))
    roles = [p.role for p in s.params]
    assert roles == ["buffer", "len", "scalar", "scalar"]
    assert "initial_value: u8" in rust_signature(s)


def test_harness_only_includes_supported():
    supported = classify_signature(_fn("crc_crc8", "uint8_t", "const uint8_t *p, uint8_t len"))
    unsupported = classify_signature(_fn("hash_fnv_1a", "void", "uint32_t len, const uint8_t *buf, uint64_t *hash"))
    h = generate_c_harness([supported, unsupported], "crc.h")
    assert "crc_crc8" in h
    assert "hash_fnv_1a" not in h  # unsupported skipped, not mis-called
