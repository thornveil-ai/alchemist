"""Byte-digest hash shape (SipHash / SHA / HMAC family) — real external lib."""

from __future__ import annotations

import ctypes
import shutil
import sys
from pathlib import Path

import pytest

from alchemist.verifier.auto_config import (
    canonical_key, classify_digest_shape, collect_subject_signatures,
    fuzz_digest_vectors, build_diff_config, _digest_binding,
)
from alchemist.verifier.auto_ffi import CSignature
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter

_GCC = shutil.which("gcc") is not None
SIP = Path(__file__).parent.parent / "subjects" / "siphash"


def _keyed_sig():
    return CSignature(name="siphash", return_type="int", params=[
        ("in", "const void *"), ("inlen", "const size_t"),
        ("k", "const void *"), ("out", "uint8_t *"), ("outlen", "const size_t")])


def _unkeyed_sig():
    return CSignature(name="sha_lite", return_type="int", params=[
        ("in", "const uint8_t *"), ("inlen", "size_t"),
        ("out", "uint8_t *"), ("outlen", "size_t")])


def test_classify_keyed_and_unkeyed_digest():
    k = classify_digest_shape(_keyed_sig())
    assert k and k.key_idx == 2 and k.out_idx == 3 and k.key_len == 16
    u = classify_digest_shape(_unkeyed_sig())
    assert u and u.key_idx is None and u.out_idx == 2


def test_scalar_checksum_is_not_a_digest():
    scalar = CSignature(name="crc32", return_type="uint32_t", params=[
        ("seed", "uint32_t"), ("buf", "const uint8_t *"), ("len", "size_t")])
    assert classify_digest_shape(scalar) is None


def test_canonical_key_is_reference_key():
    assert canonical_key(16) == bytes(range(16))


def _sip_alg():
    return AlgorithmSpec(
        name="siphash", display_name="siphash", category="hash", description="",
        return_type="Result<Vec<u8>, HashError>",
        inputs=[Parameter(name="in_", rust_type="&[u8]", description=""),
                Parameter(name="k", rust_type="&[u8]", description=""),
                Parameter(name="outlen", rust_type="usize", description="")])


@pytest.mark.skipif(not _GCC or not SIP.exists(), reason="gcc/siphash absent")
def test_digest_oracle_matches_reference_vector(tmp_path):
    from alchemist.verifier.auto_ffi import build_c_dll
    ext = ".dll" if sys.platform == "win32" else ".so"
    out = tmp_path / f"libsiphash_ref{ext}"
    r = build_c_dll([SIP / "siphash.c"], out, include_dirs=[SIP])
    assert r.success, r.stderr[:300]
    dll = ctypes.CDLL(str(out))
    sig = _keyed_sig()
    b = _digest_binding(sig, classify_digest_shape(sig))
    fn = b.load(dll)
    # Canonical SipHash-2-4: empty msg, key 00..0f, outlen 8
    assert b.adapter(fn, b"") == bytes([0x31, 0x0e, 0x0e, 0xdd, 0x47, 0xdb, 0x6f, 0x72])


@pytest.mark.skipif(not _GCC or not SIP.exists(), reason="gcc/siphash absent")
def test_digest_fuzz_vectors_render_all_inputs(tmp_path):
    from alchemist.verifier.auto_ffi import build_c_dll
    ext = ".dll" if sys.platform == "win32" else ".so"
    out = tmp_path / f"libsiphash_ref{ext}"
    build_c_dll([SIP / "siphash.c"], out, include_dirs=[SIP])
    dll = ctypes.CDLL(str(out))
    sigs = {s.name: s for s in collect_subject_signatures(SIP)}
    vecs = fuzz_digest_vectors(dll, _sip_alg(), sigs["siphash"], count=5)
    assert vecs
    v0 = vecs[0]
    assert set(v0.inputs) == {"in_", "k", "outlen"}
    assert v0.inputs["outlen"] == "8usize"
    assert v0.expected_output.startswith("Ok(vec![")
    # Empty-message vector matches the reference
    empty = next(v for v in vecs if v.inputs["in_"] == "&[]")
    assert "0x31, 0x0e, 0x0e, 0xdd, 0x47, 0xdb, 0x6f, 0x72" in empty.expected_output


def test_build_diff_config_makes_digest_harness():
    specs = [ModuleSpec(name="siphash", display_name="", description="",
                        algorithms=[_sip_alg()])]
    if not SIP.exists():
        pytest.skip("siphash subject absent")
    cfg = build_diff_config(SIP, specs)
    assert cfg is not None
    h = cfg.harnesses[0]
    assert h.digest is True
    assert h.key == bytes(range(16))
    assert h.digest_len == 8


def test_digest_adapter_emits_vec_u8_wrappers(tmp_path):
    from alchemist.verifier.adapter_gen import _resolve_digest, discover_rust_api
    from alchemist.verifier.proptest_gen import AlgorithmHarness
    (tmp_path / "siphash-hash" / "src").mkdir(parents=True)
    (tmp_path / "siphash-hash" / "Cargo.toml").write_text(
        '[package]\nname="siphash-hash"\nversion="0.1.0"\n', encoding="utf-8")
    (tmp_path / "siphash-hash" / "src" / "lib.rs").write_text(
        "pub enum HashError { Bad }\n"
        "pub fn siphash(in_: &[u8], k: &[u8], outlen: usize)"
        " -> Result<Vec<u8>, HashError> { Ok(vec![]) }\n", encoding="utf-8")
    api = discover_rust_api(tmp_path)
    h = AlgorithmHarness(algorithm="siphash", category="hash", digest=True,
                         key=bytes(range(16)), digest_len=8,
                         rust_call="rust_siphash(&input)", c_call="c_siphash(&input)")
    rw, cw, fn = _resolve_digest(h, api, "c_ref", _keyed_sig())
    assert "pub fn rust_siphash(data: &[u8]) -> Vec<u8>" in rw
    assert ".expect(" in rw  # Result unwrapped
    assert "pub fn c_siphash(data: &[u8]) -> Vec<u8>" in cw
    assert "out.as_mut_ptr()" in cw
    assert "assert" not in cw
