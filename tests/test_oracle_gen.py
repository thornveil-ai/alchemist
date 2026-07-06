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
    assert c_call_args(s) == "(const uint8_t *)in, l"


def test_seed_buffer_len():
    s = classify_signature(_fn("crc_crc32", "uint32_t", "uint32_t crc, const uint8_t *buf, uint32_t size"))
    assert [p.role for p in s.params] == ["scalar", "buffer", "len"]
    assert rust_signature(s) == "pub fn crc_crc32(crc: u32, data: &[u8]) -> u32"
    assert c_call_args(s) == "0, (const uint8_t *)in, l"


def test_buffer_len_seed():
    s = classify_signature(_fn("crc16_ccitt", "uint16_t", "const uint8_t *buf, uint32_t len, uint16_t crc"))
    assert [p.role for p in s.params] == ["buffer", "len", "scalar"]
    assert rust_signature(s) == "pub fn crc16_ccitt(data: &[u8], crc: u16) -> u16"
    assert c_call_args(s) == "(const uint8_t *)in, l, 0"


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


def test_output_buffer_classified():
    # base64's REAL signature: in + inlen + a mutable `out` buffer, returns length
    s = classify_signature(_fn("base64_encode", "unsigned int",
                               "const unsigned char *in, unsigned int inlen, char *out"))
    assert [p.role for p in s.params] == ["buffer", "len", "out_buffer"]
    assert s.supported and s.buffer_output
    assert rust_signature(s) == "pub fn base64_encode(data: &[u8]) -> Vec<u8>"


def test_output_buffer_harness_dumps_bytes():
    s = classify_signature(_fn("base64_encode", "unsigned int",
                               "const unsigned char *in, unsigned int inlen, char *out"))
    h = generate_c_harness([s], "base64.h")
    assert "fwrite(outbuf" in h            # writes produced bytes, not a scalar
    assert "base64_encode((const unsigned char *)in, l, (char *)outbuf)" in h


def test_mutable_input_pointer_not_output():
    # a mutable byte pointer NOT named like an output stays unknown (don't guess
    # in/out) — e.g. crc_crc16_ibm(uint16_t crc, uint8_t *data_blk_ptr, uint16_t size)
    s = classify_signature(_fn("crc_crc16_ibm", "uint16_t",
                               "uint16_t crc_accum, uint8_t *data_blk_ptr, uint16_t data_blk_size"))
    assert not s.supported


def test_out_length_ptr_shape():
    s = classify_signature(_fn("codec_encode", "int",
                               "const uint8_t *in, size_t inlen, uint8_t *out, size_t *outlen"))
    assert [p.role for p in s.params] == ["buffer", "len", "out_buffer", "out_length_ptr"]
    assert s.buffer_output and s.has_out_len
    assert rust_signature(s) == "pub fn codec_encode(data: &[u8]) -> Vec<u8>"


def test_out_length_ptr_harness_uses_pointer():
    s = classify_signature(_fn("codec_encode", "int",
                               "const uint8_t *in, size_t inlen, uint8_t *out, size_t *outlen"))
    h = generate_c_harness([s], "codec.h")
    assert "unsigned long __ol=0" in h
    assert "fwrite(outbuf,1,(size_t)__ol,stdout)" in h  # length from the pointer, not the return


def test_void_return_out_buffer_unsupported():
    # murmur3: void f(key,len,seed,out) writes a fixed but undeclared N bytes ->
    # can't size the output -> no honest oracle -> unsupported (not a broken green)
    s = classify_signature(_fn("MurmurHash3_x86_32", "void",
                               "const void *key, int len, uint32_t seed, void *out"))
    assert s.ret_void and s.buffer_output
    assert not s.supported


def test_scalar_return_still_supported():
    # a scalar-returning hash stays supported (ret_void guard must not over-reject)
    s = classify_signature(_fn("xxh32", "uint32_t", "const void *input, size_t len, uint32_t seed"))
    assert s.supported and not s.ret_void


def test_harness_only_includes_supported():
    supported = classify_signature(_fn("crc_crc8", "uint8_t", "const uint8_t *p, uint8_t len"))
    unsupported = classify_signature(_fn("hash_fnv_1a", "void", "uint32_t len, const uint8_t *buf, uint64_t *hash"))
    h = generate_c_harness([supported, unsupported], "crc.h")
    assert "crc_crc8" in h
    assert "hash_fnv_1a" not in h  # unsupported skipped, not mis-called
