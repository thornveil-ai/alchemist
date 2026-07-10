"""Bug 8 regression: the LLM architect non-deterministically wraps a stateless
byte codec in a Compressor/Decompressor trait (sometimes with a dangling
Self::Error that won't compile). A codec must be a FREE fn(&[u8]) -> Vec<u8> —
that's what the lift produces and what the differential harness calls.
_flatten_codec_traits drops such traits deterministically so a codec translation
is REPRODUCIBLE regardless of which crate design the architect rolled.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemist.pipeline import _flatten_codec_traits

FIX = Path(__file__).parent / "fixtures"
_HAS_GCC = shutil.which("gcc") is not None
gcc_only = pytest.mark.skipif(not _HAS_GCC, reason="gcc not on PATH")


def _method(name, sig):
    return SimpleNamespace(name=name, signature=sig, description="", has_default=False)


def _trait(name, methods):
    return SimpleNamespace(name=name, methods=methods, crate="smaz-core")


def _arch(traits):
    return SimpleNamespace(traits=traits)


@gcc_only
def test_flatten_drops_codec_traits_real_smaz():
    work = Path(tempfile.mkdtemp(prefix="alch_flat_"))
    (work / "smaz.c").write_bytes((FIX / "smaz.c").read_bytes())
    (work / "smaz.h").write_bytes((FIX / "smaz.h").read_bytes())

    arch = _arch([
        _trait("Compressor", [_method(
            "smaz_compress",
            "fn compress(&self, input: &[u8], output: &mut [u8]) -> Result<usize, Self::Error>")]),
        _trait("Decompressor", [_method(
            "smaz_decompress",
            "fn decompress(&self, input: &[u8], output: &mut [u8]) -> Result<usize, Self::Error>")]),
    ])
    specs = [SimpleNamespace(name="smaz", algorithms=[
        SimpleNamespace(name="smaz_compress"), SimpleNamespace(name="smaz_decompress")])]

    n = _flatten_codec_traits(arch, specs, work)
    assert n == 2, "both codec traits should be dropped"
    assert arch.traits == []


@gcc_only
def test_flatten_keeps_non_codec_traits_real_smaz():
    # A trait whose method is NOT a codec (unknown fn) must survive.
    work = Path(tempfile.mkdtemp(prefix="alch_flat2_"))
    (work / "smaz.c").write_bytes((FIX / "smaz.c").read_bytes())
    (work / "smaz.h").write_bytes((FIX / "smaz.h").read_bytes())

    arch = _arch([
        _trait("Compressor", [_method("smaz_compress", "fn compress(...)")]),
        _trait("Mystery", [_method("not_a_real_fn", "fn mystery(&self) -> u32")]),
    ])
    specs = [SimpleNamespace(name="smaz", algorithms=[])]
    n = _flatten_codec_traits(arch, specs, work)
    assert n == 1
    assert [t.name for t in arch.traits] == ["Mystery"]


def test_flatten_no_traits_is_noop():
    assert _flatten_codec_traits(SimpleNamespace(traits=[]), [], Path(".")) == 0
    assert _flatten_codec_traits(SimpleNamespace(traits=None), [], Path(".")) == 0
