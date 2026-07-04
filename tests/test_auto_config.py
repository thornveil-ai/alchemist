"""Subject-generic differential config + oracle bindings (M06/M09 infra).

Uses the tracked tinychk subject (3 exported checksums, incl. the unseeded
u16 fletcher16) as the reference non-zlib subject.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter
from alchemist.verifier.auto_config import (
    build_diff_config,
    classify_checksum_shape,
    collect_subject_signatures,
    default_seed,
    make_checksum_bindings,
)
from alchemist.verifier.auto_ffi import CSignature

TINYCHK = Path(__file__).parent.parent / "subjects" / "tinychk"

_GCC = shutil.which("gcc") is not None


def _alg(name: str, ret: str, inputs: list[tuple[str, str]]) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name, display_name=name, category="checksum", description="",
        inputs=[Parameter(name=n, rust_type=t, description="") for n, t in inputs],
        return_type=ret,
    )


def _tinychk_specs() -> list[ModuleSpec]:
    return [ModuleSpec(name="tinychk", display_name="", description="", algorithms=[
        _alg("adler32", "u32",
             [("seed", "u32"), ("buf", "&[u8]"), ("len", "usize")]),
        _alg("crc32", "u32",
             [("seed", "u32"), ("buf", "&[u8]"), ("len", "usize")]),
        _alg("fletcher16", "u16",
             [("buf", "&[u8]"), ("len", "usize")]),
    ])]


# ---------- shape classification ----------

def test_shape_classification():
    seeded = CSignature(name="adler32", return_type="uint32_t",
                        params=[("seed", "uint32_t"),
                                ("buf", "const uint8_t *"),
                                ("len", "size_t")])
    unseeded = CSignature(name="fletcher16", return_type="uint16_t",
                          params=[("buf", "const uint8_t *"),
                                  ("len", "size_t")])
    weird = CSignature(name="compress", return_type="int",
                       params=[("dest", "Bytef *"), ("destLen", "uLongf *"),
                               ("source", "const Bytef *"),
                               ("sourceLen", "uLong")])
    assert classify_checksum_shape(seeded) == "seeded"
    assert classify_checksum_shape(unseeded) == "unseeded"
    assert classify_checksum_shape(weird) is None


def test_default_seeds():
    assert default_seed("adler32") == 1
    assert default_seed("crc32") == 0
    assert default_seed("fletcher16") == 0


# ---------- header collection on the real subject ----------

def test_collect_tinychk_signatures():
    sigs = {s.name: s for s in collect_subject_signatures(TINYCHK)}
    assert set(sigs) >= {"adler32", "crc32", "fletcher16"}
    assert classify_checksum_shape(sigs["adler32"]) == "seeded"
    assert classify_checksum_shape(sigs["fletcher16"]) == "unseeded"


# ---------- config derivation ----------

def test_build_diff_config_for_tinychk():
    cfg = build_diff_config(TINYCHK, _tinychk_specs())
    assert cfg is not None
    by_name = {h.algorithm: h for h in cfg.harnesses}
    assert set(by_name) == {"adler32", "crc32", "fletcher16"}
    assert by_name["adler32"].seed == 1
    assert by_name["crc32"].seed == 0
    assert by_name["fletcher16"].seed is None
    assert 5552 in by_name["adler32"].boundary_lengths
    assert cfg.ffi_crate_name == "c_tinychk_ref"
    assert any(p.name == "tinychk.c" for p in cfg.c_sources)
    # fletcher16's signature is among the FFI decls
    assert any(s.name == "fletcher16" for s in cfg.c_public_signatures)


def test_build_diff_config_refuses_without_specs():
    assert build_diff_config(TINYCHK, None) is None
    assert build_diff_config(TINYCHK, []) is None


def test_build_diff_config_refuses_unmatched_subject(tmp_path):
    (tmp_path / "thing.h").write_text(
        "void frobnicate(struct ctx *c);\n", encoding="utf-8")
    (tmp_path / "thing.c").write_text("int x;\n", encoding="utf-8")
    specs = [ModuleSpec(name="m", display_name="", description="", algorithms=[
        _alg("frobnicate", "()", [("c", "&mut Ctx")]),
    ])]
    specs[0].algorithms[0].category = "utility"
    assert build_diff_config(tmp_path, specs) is None


# ---------- bindings against the real compiled oracle ----------

def _fletcher16_model(data: bytes) -> int:
    s1 = s2 = 0
    for b in data:
        s1 = (s1 + b) % 255
        s2 = (s2 + s1) % 255
    return (s2 << 8) | s1


@pytest.mark.skipif(not _GCC, reason="gcc not on PATH")
def test_bindings_execute_against_subject_oracle(tmp_path):
    """Compile tinychk into a DLL and cross-check the auto-binding for the
    unseeded u16 shape against an independent Python model."""
    import ctypes
    from alchemist.verifier.auto_ffi import build_c_dll
    import sys
    ext = ".dll" if sys.platform == "win32" else ".so"
    out = tmp_path / f"libtinychk_ref{ext}"
    r = build_c_dll([TINYCHK / "tinychk.c"], out, include_dirs=[TINYCHK])
    assert r.success, r.stderr[:400]
    dll = ctypes.CDLL(str(out))
    algs = _tinychk_specs()[0].algorithms
    bindings = make_checksum_bindings(collect_subject_signatures(TINYCHK), algs)
    assert set(bindings) == {"adler32", "crc32", "fletcher16"}
    fl = bindings["fletcher16"]
    fn = fl.load(dll)
    for data in (b"", b"a", b"abcde", bytes(range(200)) * 3):
        assert fl.adapter(fn, data) == _fletcher16_model(data)
    # Seeded shape sanity: adler32 of "Wikipedia" with seed 1 (RFC 1950)
    ad = bindings["adler32"]
    assert ad.adapter(ad.load(dll), b"Wikipedia") == 0x11E60398


@pytest.mark.skipif(not _GCC, reason="gcc not on PATH")
def test_generic_backfill_mints_oracle_tagged_vectors():
    """End-to-end: non-zlib subject gets vectors from its own compiled C."""
    from alchemist.extractor.oracle_tags import is_tagged
    from alchemist.implementer.tdd_generator import TDDGenerator
    specs = _tinychk_specs()
    gen = TDDGenerator.__new__(TDDGenerator)
    gen._source_root = TINYCHK
    gen._backfill_fuzz_vectors(specs)
    fletcher = specs[0].algorithms[2]
    assert fletcher.test_vectors, "no vectors minted for fletcher16"
    v = fletcher.test_vectors[0]
    assert is_tagged(v)
    assert "tinychk_ref" in v.source
    assert v.expected_output.endswith("u16")
    # len param rendered as the buffer's true length, not data-derived bytes
    for vec in fletcher.test_vectors:
        buf_lit = vec.inputs["buf"]
        n_items = 0 if buf_lit == "&[]" else buf_lit.count(",") + 1
        assert vec.inputs["len"] == f"{n_items}usize"
