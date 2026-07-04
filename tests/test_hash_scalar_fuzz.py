"""A scalar-returning 'hash' function is fuzzed as a checksum, not a digest."""

from __future__ import annotations

import ctypes
import shutil
from pathlib import Path

import pytest

from alchemist.extractor.fuzz_vectors import fuzz_for_spec, CFunctionBinding
from alchemist.extractor.schemas import AlgorithmSpec, Parameter

_GCC = shutil.which("gcc") is not None
HASHKIT = Path(__file__).parent.parent / "subjects" / "hashkit"


def _fnv_alg():
    return AlgorithmSpec(
        name="fnv1a32", display_name="fnv1a32", category="hash",
        description="", return_type="u32",
        inputs=[Parameter(name="buf", rust_type="&[u8]", description="")])


@pytest.mark.skipif(not _GCC or not HASHKIT.exists(), reason="gcc/hashkit absent")
def test_scalar_hash_gets_checksum_vectors(tmp_path):
    from alchemist.verifier.auto_ffi import build_c_dll
    from alchemist.verifier.auto_config import (
        collect_subject_signatures, make_checksum_bindings,
    )
    import sys
    ext = ".dll" if sys.platform == "win32" else ".so"
    out = tmp_path / f"libhashkit_ref{ext}"
    r = build_c_dll([HASHKIT / "hashkit.c"], out, include_dirs=[HASHKIT])
    assert r.success, r.stderr[:300]
    dll = ctypes.CDLL(str(out))
    alg = _fnv_alg()
    bindings = make_checksum_bindings(
        collect_subject_signatures(HASHKIT), [alg])
    vecs = fuzz_for_spec(dll, alg, bindings)
    assert vecs, "scalar hash produced no vectors (routed to digest fuzzer?)"
    assert all(v.expected_output.endswith("u32") for v in vecs)
    # FNV-1a("abc") == 0x1a47e90b
    abc = next((v for v in vecs if v.inputs.get("buf") == "&[0x61, 0x62, 0x63]"), None)
    if abc:
        assert abc.expected_output == f"{0x1a47e90b}u32"
