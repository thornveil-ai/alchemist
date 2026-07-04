"""Tests for the zlib checksum shim (compiled-C oracle for crc32.c locals).

zlib's crc_word / crc_word_big / multmodp / x2nmodp are `local` (static)
in crc32.c, so zlib1.dll never exports them. zlib_checksum_shim.dll
amalgamates crc32.c into its own compile unit and re-exports them with
fixed-width signatures, pinned to the braided W=8 / N=5 configuration
(the x86_64 gcc default that the pure-Python references model).

These tests are the independent validation that the compiled C and the
pure-Python references in fuzz_vectors.py agree bit-for-bit — in
particular that the W=8 crc_word_big fix matches real compiled zlib.
"""

from __future__ import annotations

import ctypes
import struct
from pathlib import Path

import pytest

from alchemist.extractor.c_shim_fuzz import (
    ZLIB_CHECKSUM_SHIM_PURE_BINDINGS,
    crosscheck_checksum_shim,
    fuzz_pure_shim,
    locate_zlib_checksum_shim,
)
from alchemist.extractor.fuzz_vectors import (
    _crc_word_pure_ref,
    _crc_word_big_pure_ref,
    _multmodp_pure_ref,
    _x2nmodp_pure_ref,
)
from alchemist.extractor.schemas import AlgorithmSpec, Parameter


DLL_PATH = (
    Path(__file__).parent.parent
    / "subjects" / "zlib" / "shim" / "zlib_checksum_shim.dll"
)

pytestmark = pytest.mark.skipif(
    not DLL_PATH.exists(), reason="zlib_checksum_shim.dll not built"
)


def _load() -> ctypes.CDLL:
    return ctypes.CDLL(str(DLL_PATH))


def _crc_spec(name: str, ret: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name,
        display_name=name,
        category="checksum",
        description="",
        inputs=[Parameter(name="data", rust_type="u64", description="")],
        return_type=ret,
    )


# ---------- DLL load + configuration pins ----------

def test_dll_loads_and_config_pins():
    dll = _load()
    w_fn = dll.shim_crc_w
    w_fn.restype = ctypes.c_int32
    n_fn = dll.shim_crc_n
    n_fn.restype = ctypes.c_int32
    assert int(w_fn()) == 8, "shim must be the braided W=8 build"
    assert int(n_fn()) == 5, "shim must be the N=5 build"


def test_locator_finds_dll(monkeypatch):
    # locate_zlib_checksum_shim resolves cwd-relative paths; pin cwd to
    # the repo root so the test doesn't depend on the pytest invocation dir.
    monkeypatch.chdir(Path(__file__).parent.parent)
    found = locate_zlib_checksum_shim()
    assert found is not None
    assert found.name == "zlib_checksum_shim.dll"


# ---------- Known anchors: shim == corrected pure-Python reference ----------

def test_crc_word_big_known_anchors():
    dll = _load()
    fn = dll.shim_run_crc_word_big
    fn.argtypes = [ctypes.c_uint64]
    fn.restype = ctypes.c_uint64
    # Zero fixed point (no pre/post conditioning).
    assert int(fn(0)) == 0
    # Independent validation of the W=8 fix: the compiled zlib output must
    # equal the corrected pure reference for the LE byte-input convention.
    for v in (1, 0xFF, 0x636261):  # 0x636261 == b"abc" packed LE
        shim_out = int(fn(ctypes.c_uint64(v)))
        pure_out = _crc_word_big_pure_ref(v.to_bytes(8, "little"))
        assert shim_out == pure_out, (
            f"crc_word_big({v:#x}): shim={shim_out:#018x} pure={pure_out:#018x}"
        )
    # Hard anchor from zlib's shipped W=8 crc32.h: crc_big_table[1] rides
    # in the HIGH 32 bits.
    assert int(fn(ctypes.c_uint64(1))) == 0x9630077700000000


def test_crc_word_known_anchors():
    dll = _load()
    fn = dll.shim_run_crc_word
    fn.argtypes = [ctypes.c_uint64]
    fn.restype = ctypes.c_uint32
    assert int(fn(0)) == 0
    for v in (1, 0xFF, 0x636261):
        shim_out = int(fn(ctypes.c_uint64(v)))
        pure_out = _crc_word_pure_ref(v.to_bytes(8, "little"))
        assert shim_out == pure_out, (
            f"crc_word({v:#x}): shim={shim_out:#010x} pure={pure_out:#010x}"
        )


def test_multmodp_known_anchors():
    dll = _load()
    fn = dll.shim_run_multmodp
    fn.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    fn.restype = ctypes.c_uint32
    # Anchor from the existing generated tests.
    assert int(fn(0xFFFFFFFF, 0xFFFFFFFF)) == 1048090088
    # x^0 (reflected: 1 << 31) is the multiplicative identity.
    assert int(fn(0x80000000, 0xDEADBEEF)) == 0xDEADBEEF
    for a, b in ((1, 1), (0xEDB88320, 0xEDB88320), (0x12345678, 0x9ABCDEF0)):
        shim_out = int(fn(ctypes.c_uint32(a), ctypes.c_uint32(b)))
        pure_out = _multmodp_pure_ref(struct.pack("<II", a, b))
        assert shim_out == pure_out, (
            f"multmodp({a:#x}, {b:#x}): shim={shim_out:#010x} pure={pure_out:#010x}"
        )


def test_x2nmodp_known_anchors():
    dll = _load()
    fn = dll.shim_run_x2nmodp
    fn.argtypes = [ctypes.c_int64, ctypes.c_uint32]
    fn.restype = ctypes.c_uint32
    assert int(fn(0, 0)) == 0x80000000  # x^0 == 1, reflected
    assert int(fn(255, 0)) == 28704029
    for n, k in ((1, 0), (1, 3), (0xFFFFFFFF, 31)):
        shim_out = int(fn(ctypes.c_int64(n), ctypes.c_uint32(k)))
        pure_out = _x2nmodp_pure_ref(struct.pack("<QI", n, k))
        assert shim_out == pure_out, (
            f"x2nmodp({n:#x}, {k:#x}): shim={shim_out:#010x} pure={pure_out:#010x}"
        )


# ---------- Oracle-integrity cross-check ----------

def test_crosscheck_returns_no_mismatches():
    dll = _load()
    assert crosscheck_checksum_shim(dll) == []


# ---------- Vector generation through the binding registry ----------

def test_fuzz_pure_shim_crc_word_big_vectors():
    dll = _load()
    binding = ZLIB_CHECKSUM_SHIM_PURE_BINDINGS["crc_word_big"]
    vectors = fuzz_pure_shim(
        dll, _crc_spec("crc_word_big", "u64"), binding, count=20,
    )
    assert len(vectors) == 20
    for v in vectors:
        assert "shim" in v.source
        # Inputs render as u64-suffixed Rust literals for the generated
        # call `super::crc_word_big(data)`.
        data_lit = v.inputs["data"]
        assert data_lit.endswith("u64")
        int(data_lit[:-3])  # numeric prefix parses
        # Expected outputs likewise must be valid u64 literals.
        assert v.expected_output.endswith("u64")
        out_val = int(v.expected_output[:-3])
        assert 0 <= out_val <= 0xFFFFFFFFFFFFFFFF


def test_fuzz_pure_shim_crc_word_vectors_are_u32():
    dll = _load()
    binding = ZLIB_CHECKSUM_SHIM_PURE_BINDINGS["crc_word"]
    vectors = fuzz_pure_shim(
        dll, _crc_spec("crc_word", "u32"), binding, count=8,
    )
    assert len(vectors) == 8
    for v in vectors:
        assert v.inputs["data"].endswith("u64")
        assert v.expected_output.endswith("u32")
        assert 0 <= int(v.expected_output[:-3]) <= 0xFFFFFFFF


def test_fuzz_pure_shim_multmodp_never_fuzzes_a_zero():
    # a == 0 hangs the compiled C oracle (documented zlib precondition).
    # If this test itself completes, the oracle didn't hang; also verify
    # the rendered `a` literals directly.
    dll = _load()
    binding = ZLIB_CHECKSUM_SHIM_PURE_BINDINGS["multmodp"]
    vectors = fuzz_pure_shim(
        dll, _crc_spec("multmodp", "u32"), binding, count=32,
    )
    assert len(vectors) == 32
    for v in vectors:
        assert v.inputs["a"].endswith("u32")
        assert int(v.inputs["a"][:-3]) != 0
        assert v.expected_output.endswith("u32")


def test_fuzz_pure_shim_x2nmodp_vectors():
    dll = _load()
    binding = ZLIB_CHECKSUM_SHIM_PURE_BINDINGS["x2nmodp"]
    vectors = fuzz_pure_shim(
        dll, _crc_spec("x2nmodp", "u32"), binding, count=16,
    )
    assert len(vectors) == 16
    for v in vectors:
        # Rust hardport takes (n: u64, k: u32); C side is (z_off64_t, unsigned),
        # so fuzzed n must stay below 2^63.
        n_lit = v.inputs["n"]
        assert n_lit.endswith("u64")
        assert 0 <= int(n_lit[:-3]) < (1 << 63)
        assert v.inputs["k"].endswith("u32")
        assert v.expected_output.endswith("u32")
