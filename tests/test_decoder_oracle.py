"""Round-trip decoder oracle: decoders must be fuzzed with VALID encoded
streams (minted by their paired encoder), not random bytes. Random bytes drive
a C decoder off the end of a truncated frame (undefined behavior) which no
memory-safe Rust translation can match — the historical cause of
smaz_decompress failing its differential forever.
"""

from __future__ import annotations

import ctypes
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemist.verifier.auto_config import (
    _paired_encoder_name, fuzz_buf_transform_vectors,
)
from alchemist.verifier.auto_ffi import build_c_dll, parse_header

FIX = Path(__file__).parent / "fixtures"
_HAS_GCC = shutil.which("gcc") is not None
gcc_only = pytest.mark.skipif(not _HAS_GCC, reason="gcc not on PATH")


def test_decoder_proptest_uses_encoder_roundtrip():
    from alchemist.verifier.proptest_gen import (
        AlgorithmHarness, _proptest_buf_transform_block,
    )
    dec = AlgorithmHarness(
        algorithm="smaz_decompress", category="buf_transform",
        rust_call="rust_smaz_decompress(&input)", c_call="c_smaz_decompress(&input)",
        encoder_c_call="c_smaz_compress(&pt)", cases=4000,
    )
    block = _proptest_buf_transform_block(dec)
    assert "pt in " in block                       # fuzzes plaintext
    assert "let input = c_smaz_compress(&pt);" in block   # mints a valid stream
    assert "rust_smaz_decompress(&input)" in block

    enc = AlgorithmHarness(
        algorithm="smaz_compress", category="buf_transform",
        rust_call="rust_smaz_compress(&input)", c_call="c_smaz_compress(&input)",
        cases=4000,  # no encoder_c_call -> plain random-byte strategy
    )
    eblock = _proptest_buf_transform_block(enc)
    assert "input in " in eblock
    assert "let input =" not in eblock


def test_paired_encoder_name():
    assert _paired_encoder_name("smaz_decompress") == "smaz_compress"
    assert _paired_encoder_name("tinf_uncompress") == "tinf_compress"
    assert _paired_encoder_name("base64_decode") == "base64_encode"
    assert _paired_encoder_name("zlib_inflate") == "zlib_deflate"
    # encoders and non-codecs are NOT decoders
    assert _paired_encoder_name("smaz_compress") is None
    assert _paired_encoder_name("sha256") is None


@gcc_only
def test_decoder_fuzz_inputs_are_valid_streams_real_smaz():
    """Every input the fuzzer mints for smaz_decompress must be a VALID smaz
    stream: round-trip stable under the real codec (compress(decompress(x))==x).
    That is only possible because inputs come from the paired encoder."""
    tmp = Path(tempfile.mkdtemp(prefix="alch_dec_oracle_"))
    ext = ".dll" if __import__("os").name == "nt" else ".so"
    dll_path = tmp / f"smaz{ext}"
    r = build_c_dll([FIX / "smaz.c"], dll_path)
    assert r.success, r.stderr
    dll = ctypes.CDLL(str(dll_path))

    sig = next(s for s in parse_header((FIX / "smaz.h").read_text())
               if s.name == "smaz_decompress")
    alg = SimpleNamespace(
        name="smaz_decompress",
        inputs=[SimpleNamespace(name="in_", rust_type="&[u8]")],
        return_type="Vec<u8>",
    )

    vectors = fuzz_buf_transform_vectors(dll, alg, sig, count=40)
    assert len(vectors) > 0

    # Bind C compress + decompress to check round-trip stability of each input.
    def _bind(name):
        fn = getattr(dll, name)
        fn.restype = ctypes.c_int
        fn.argtypes = (ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int,
                       ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int)
        return fn

    comp, decomp = _bind("smaz_compress"), _bind("smaz_decompress")

    def _call(fn, data: bytes) -> bytes:
        ib = (ctypes.c_ubyte * len(data))(*data) if data else (ctypes.c_ubyte * 1)()
        cap = len(data) * 8 + 1024
        ob = (ctypes.c_ubyte * cap)()
        ret = int(fn(ib, len(data), ob, cap))
        assert 0 <= ret <= cap, f"sentinel/overflow ret={ret}"
        return bytes(ob[i] for i in range(ret))

    # Parse each vector's input literal back to bytes and assert validity.
    checked = 0
    for v in vectors:
        lit = v.inputs["in_"]                     # e.g. "&[0x02, 0x73, ...]" or "&[]"
        nums = [int(x, 16) for x in __import__("re").findall(r"0x([0-9a-fA-F]+)", lit)]
        stream = bytes(nums)
        # Valid stream <=> compress(decompress(stream)) == stream (round-trip stable)
        decoded = _call(decomp, stream)
        re_encoded = _call(comp, decoded)
        assert re_encoded == stream, (
            f"input is NOT a valid smaz stream (round-trip unstable): "
            f"{stream!r} -> {decoded!r} -> {re_encoded!r}")
        checked += 1
    assert checked == len(vectors)
