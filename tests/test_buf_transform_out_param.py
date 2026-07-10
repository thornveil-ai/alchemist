"""Bug 5 regression: a buf_transform codec's OUTPUT buffer param must be dropped
from the lifted Rust signature. C `int f(char *in, int inlen, char *out, int
outlen)` has TWO char* params; `out` is not const, so it lifts to `&[u8]`
(no `mut`) and the old mut-only drop-heuristic kept it as a phantom second
input. The test harness calls the fn with ONE arg, so the arity mismatch made
smaz's fills unwinnable. normalize_digest_specs must keep only the input slice.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemist.verifier.auto_config import normalize_digest_specs

FIX = Path(__file__).parent / "fixtures"
_HAS_GCC = shutil.which("gcc") is not None
gcc_only = pytest.mark.skipif(not _HAS_GCC, reason="gcc not on PATH")


def _spec_module(algs):
    return SimpleNamespace(algorithms=algs)


@gcc_only
def test_buf_transform_drops_out_param_real_smaz():
    # Copy the real smaz sources into a work dir so collect_subject_signatures
    # sees smaz_compress / smaz_decompress with their real (in,inlen,out,outlen).
    work = Path(tempfile.mkdtemp(prefix="alch_bufsig_"))
    (work / "smaz.c").write_bytes((FIX / "smaz.c").read_bytes())
    (work / "smaz.h").write_bytes((FIX / "smaz.h").read_bytes())

    # Simulate the generic lift: BOTH char* params became &[u8] (out is not const).
    def _mk(name):
        return SimpleNamespace(
            name=name,
            inputs=[SimpleNamespace(name="in_", rust_type="&[u8]"),
                    SimpleNamespace(name="inlen", rust_type="usize"),
                    SimpleNamespace(name="out", rust_type="&[u8]"),
                    SimpleNamespace(name="outlen", rust_type="usize")],
            outputs=[],
            return_type="i32",
        )
    comp, decomp = _mk("smaz_compress"), _mk("smaz_decompress")
    n = normalize_digest_specs(work, [_spec_module([comp, decomp])])

    assert n == 2, "both codecs should be normalized"
    for alg in (comp, decomp):
        names = [p.name for p in alg.inputs]
        assert names == ["in_"], f"{alg.name}: expected only the input slice, got {names}"
        assert alg.return_type == "Vec<u8>"
        assert alg.outputs == []


def test_buf_transform_out_param_no_gcc_smoke():
    # Without gcc we can't compile the oracle, so normalize is a no-op (0). Just
    # assert it doesn't crash on a spec whose sig can't be resolved.
    m = _spec_module([SimpleNamespace(
        name="nonexistent_fn",
        inputs=[SimpleNamespace(name="in_", rust_type="&[u8]")],
        outputs=[], return_type="i32")])
    # points at an empty dir -> no signatures -> nothing normalized
    empty = Path(tempfile.mkdtemp(prefix="alch_empty_"))
    assert normalize_digest_specs(empty, [m]) == 0
