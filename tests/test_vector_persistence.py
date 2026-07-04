"""Fuzz-vector persistence + oracle provenance tags (G4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alchemist.extractor.oracle_tags import (
    is_tagged,
    oracle_tag_for_callable,
    oracle_tag_for_file,
    strip_tag,
    tag_vectors,
)
from alchemist.extractor.schemas import (
    AlgorithmSpec,
    ModuleSpec,
    Parameter,
    TestVector,
)
from alchemist.implementer.tdd_generator import TDDGenerator

_ZLIB_DLL = Path("verify/zlib1.dll")

pytestmark = pytest.mark.skipif(
    not _ZLIB_DLL.exists(),
    reason="reference zlib1.dll not built (run from repo root with verify/ present)",
)


def _crc_word_big_alg() -> AlgorithmSpec:
    return AlgorithmSpec(
        name="crc_word_big",
        display_name="crc_word_big",
        category="checksum",
        description="big-endian braided CRC word step",
        inputs=[Parameter(name="data", rust_type="u64", description="")],
        return_type="u64",
        referenced_standards=["CRC-32", "variant:ieee_reflected"],
    )


def _authored_alg() -> AlgorithmSpec:
    return AlgorithmSpec(
        name="crc32_z",
        display_name="crc32_z",
        category="checksum",
        description="",
        inputs=[Parameter(name="buf", rust_type="&[u8]", description="")],
        return_type="u32",
        test_vectors=[TestVector(
            description="authored by a human",
            inputs={"buf": 'b"abc"'},
            expected_output="0x352441c2u32",
            tolerance="exact",
            source="RFC 1952 worked example",  # no oracle tag — authored
        )],
    )


def _module() -> ModuleSpec:
    return ModuleSpec(
        name="crc32", display_name="", description="",
        algorithms=[_crc_word_big_alg(), _authored_alg()],
    )


def _backfill(specs, specs_dir=None):
    gen = TDDGenerator.__new__(TDDGenerator)  # no LLM client
    gen._backfill_fuzz_vectors(specs, specs_dir=specs_dir)


# ---------- tag helpers ----------

def test_tag_roundtrip_and_idempotence():
    v = TestVector(description="d", inputs={"x": "1"}, expected_output="2",
                   tolerance="exact", source="pure Python reference: f")
    tag_vectors([v], "pyref:f:0123456789abcdef")
    assert is_tagged(v)
    assert v.source.endswith("[oracle:pyref:f:0123456789abcdef]")
    # Re-tagging replaces, never stacks
    tag_vectors([v], "shim:x.dll:fedcba9876543210")
    assert v.source.count("[oracle:") == 1
    assert strip_tag(v.source) == "pure Python reference: f"


def test_tag_for_file_hashes_content(tmp_path):
    f = tmp_path / "oracle.dll"
    f.write_bytes(b"v1")
    t1 = oracle_tag_for_file("shim", f)
    f.write_bytes(b"v2")
    t2 = oracle_tag_for_file("shim", f)
    assert t1 != t2 and t1.startswith("shim:oracle.dll:")


def test_tag_for_callable_tracks_source():
    t = oracle_tag_for_callable("pyref", strip_tag)
    assert t.startswith("pyref:strip_tag:")


# ---------- backfill policy ----------

def test_generated_vectors_are_tagged_and_authored_untouched():
    specs = [_module()]
    _backfill(specs)
    crc_word_big = specs[0].algorithms[0]
    authored = specs[0].algorithms[1]
    assert crc_word_big.test_vectors, "backfill produced no vectors"
    assert all(is_tagged(v) for v in crc_word_big.test_vectors)
    # The authored vector is byte-identical and untagged
    assert authored.test_vectors[0].source == "RFC 1952 worked example"
    assert not is_tagged(authored.test_vectors[0])


def test_tagged_vectors_regenerate_instead_of_being_trusted():
    """A stale persisted vector must never shadow a fixed oracle."""
    specs = [_module()]
    alg = specs[0].algorithms[0]
    alg.test_vectors = [TestVector(
        description="stale", inputs={"data": "1u64"},
        expected_output="999u64",  # wrong on purpose
        tolerance="exact",
        source="pure Python reference: crc_word_big [oracle:pyref:old:0000000000000000]",
    )]
    _backfill(specs)
    assert alg.test_vectors, "regeneration produced nothing"
    assert all(v.expected_output != "999u64" for v in alg.test_vectors)
    assert all(is_tagged(v) for v in alg.test_vectors)


def test_vectors_persist_into_spec_checkpoint(tmp_path):
    specs = [_module()]
    checkpoint = tmp_path / "crc32.json"
    checkpoint.write_text(specs[0].model_dump_json(indent=2), encoding="utf-8")
    _backfill(specs, specs_dir=tmp_path)
    on_disk = json.loads(checkpoint.read_text(encoding="utf-8"))
    algs = {a["name"]: a for a in on_disk["algorithms"]}
    assert algs["crc_word_big"]["test_vectors"], "vectors not persisted"
    assert "[oracle:" in algs["crc_word_big"]["test_vectors"][0]["source"]
    # Round-trip: reloading and re-running backfill regenerates (tagged) and
    # keeps the file loadable
    reloaded = [ModuleSpec.model_validate(on_disk)]
    _backfill(reloaded, specs_dir=tmp_path)
    assert reloaded[0].algorithms[0].test_vectors


def test_no_spec_file_is_created_uninvited(tmp_path):
    specs = [_module()]
    _backfill(specs, specs_dir=tmp_path)  # dir has no crc32.json
    assert not (tmp_path / "crc32.json").exists()


# ---------- oracle integrity: stop-the-line + unavailable-oracle restore ----------

def test_disputed_oracle_stops_the_line(monkeypatch):
    """A shim-vs-reference disagreement must raise, and no caller may see
    partially regenerated state: the raise happens before any clearing."""
    import alchemist.extractor.c_shim_fuzz as csf
    from alchemist.extractor.oracle_tags import OracleDisputeError
    if csf.locate_zlib_checksum_shim() is None:
        pytest.skip("checksum shim DLL not built")
    monkeypatch.setattr(
        csf, "crosscheck_checksum_shim",
        lambda dll: ["crc_word_big(1): shim=0x1 pyref=0x2"],
    )
    specs = [_module()]
    planted = [TestVector(
        description="previously minted", inputs={"data": "1u64"},
        expected_output="1u64", tolerance="exact",
        source="C reference via shim [oracle:shim:zlib_checksum_shim.dll:0000000000000000]",
    )]
    specs[0].algorithms[0].test_vectors = list(planted)
    with pytest.raises(OracleDisputeError):
        _backfill(specs)
    # Vectors were not cleared: the dispute fired before regeneration began.
    assert specs[0].algorithms[0].test_vectors == planted


def test_solo_reraises_disputed_oracle():
    """solo's broad backfill except must NOT swallow OracleDisputeError."""
    import inspect
    import alchemist.solo as solo_mod
    src = inspect.getsource(solo_mod)
    assert "except OracleDisputeError" in src
    idx_dispute = src.index("except OracleDisputeError")
    idx_broad = src.index("except Exception", idx_dispute)
    assert idx_dispute < idx_broad, "dispute handler must precede broad except"


def test_unavailable_oracle_restores_vectors_instead_of_zeroing(tmp_path):
    """Tagged vectors whose oracle is absent on this machine must survive —
    zero vectors would reopen the compile-only-pass loophole and, with
    persistence, durably delete them from the checkpoint."""
    orphan = AlgorithmSpec(
        name="shim_only_orphan_fn",
        display_name="",
        category="utility",
        description="",
        inputs=[Parameter(name="x", rust_type="u32", description="")],
        return_type="u32",
        test_vectors=[TestVector(
            description="minted by a shim this machine has not built",
            inputs={"x": "1u32"}, expected_output="2u32", tolerance="exact",
            source="C reference via shim [oracle:shim:missing_shim.dll:1111111111111111]",
        )],
    )
    module = ModuleSpec(name="orphans", display_name="", description="",
                        algorithms=[orphan, _crc_word_big_alg()])
    checkpoint = tmp_path / "orphans.json"
    checkpoint.write_text(module.model_dump_json(indent=2), encoding="utf-8")
    _backfill([module], specs_dir=tmp_path)
    # crc_word_big regenerated (touching the module) but the orphan's
    # vectors were restored, in memory and on disk.
    assert orphan.test_vectors and orphan.test_vectors[0].expected_output == "2u32"
    on_disk = json.loads(checkpoint.read_text(encoding="utf-8"))
    disk_orphan = next(a for a in on_disk["algorithms"]
                       if a["name"] == "shim_only_orphan_fn")
    assert disk_orphan["test_vectors"], "checkpoint vectors were deleted"


def test_hardport_lookup_tries_snaked_name():
    """Spec algorithm names with display punctuation must still find their
    hardport file (named after the emitted Rust fn)."""
    gen = TDDGenerator.__new__(TDDGenerator)
    p = gen._hardport_path(
        "zlib", "zlib-checksum", "crc32", "main (inftrees.c generator)",
    )
    assert p is not None and p.name == "main_inftrees_c_generator_.rs"
