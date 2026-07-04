"""Tests for the Stage 5 mandatory differential gate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from alchemist.implementer.anti_stub import ScanReport
from alchemist.verifier.differential_tester import (
    DifferentialConfig,
    DifferentialTester,
    GateResult,
    VerificationReport,
    verify_workspace,
)


def _fake_gate(name: str, ok: bool, summary: str = "") -> GateResult:
    return GateResult(name=name, passed=ok, summary=summary)


def test_report_passed_requires_all_gates():
    r = VerificationReport(
        compile=_fake_gate("compile", True),
        anti_stub=_fake_gate("anti-stub", True),
        no_unsafe=_fake_gate("no-unsafe", True),
        semantic=_fake_gate("semantic", True),
        test=_fake_gate("test", True),
        differential=_fake_gate("differential", True),
    )
    assert r.passed


def test_report_fails_if_any_gate_fails():
    for fail in ("compile", "anti_stub", "no_unsafe", "semantic", "test", "differential"):
        gates = {
            "compile": _fake_gate("compile", True),
            "anti_stub": _fake_gate("anti-stub", True),
            "no_unsafe": _fake_gate("no-unsafe", True),
            "semantic": _fake_gate("semantic", True),
            "test": _fake_gate("test", True),
            "differential": _fake_gate("differential", True),
        }
        gates[fail] = _fake_gate(fail, False, "simulated failure")
        r = VerificationReport(**gates)
        assert not r.passed
        assert r.first_failure is not None


def test_missing_diff_config_refuses_success(tmp_path):
    """If no diff_config is supplied, the gate must refuse to declare success."""
    # Make a throwaway Cargo workspace so compile/test commands run cleanly
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "dummy"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("pub fn ok() -> u32 { 42 }\n", encoding="utf-8")

    tester = DifferentialTester(tmp_path, diff_config=None)
    result = tester.gate_differential()
    assert not result.passed
    assert "REFUSING" in result.summary


def test_run_all_short_circuits_on_compile_failure(tmp_path):
    # Compile-failing workspace
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "broken"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("fn broken( -> {\n", encoding="utf-8")

    tester = DifferentialTester(tmp_path)
    with patch.object(tester, "gate_test") as mock_test, \
         patch.object(tester, "gate_differential") as mock_diff:
        report = tester.run_all()
        # Tests and diff must NOT have been invoked when compile fails
        mock_test.assert_not_called()
        mock_diff.assert_not_called()
    assert not report.compile.passed
    assert not report.passed


def test_anti_stub_gate_is_informational_even_on_compile_failure(tmp_path):
    """We still want anti-stub results when compile fails, for diagnostics."""
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "broken"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(
        "pub fn x() { unimplemented!() }\n", encoding="utf-8")

    tester = DifferentialTester(tmp_path)
    report = tester.run_all()
    assert report.anti_stub.anti_stub_report is not None
    assert not report.anti_stub.passed


def test_verify_workspace_is_public_api(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "broken"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(
        "pub fn x() { unimplemented!() }\n", encoding="utf-8")

    report = verify_workspace(tmp_path)
    # Must return a VerificationReport; compile may or may not pass
    assert isinstance(report, VerificationReport)


def test_verification_summary_string_contains_all_gates():
    r = VerificationReport(
        compile=_fake_gate("compile", True, "clean"),
        anti_stub=_fake_gate("anti-stub", False, "3 violations"),
        no_unsafe=_fake_gate("no-unsafe", True, "zero unsafe"),
        semantic=_fake_gate("semantic", True, "clean"),
        test=_fake_gate("test", True, "10 passed"),
        differential=_fake_gate("differential", False, "no config"),
    )
    s = r.summary()
    assert "compile" in s
    assert "anti-stub" in s
    assert "semantic" in s
    assert "test" in s
    assert "diff" in s
    assert "FAIL" in s


# ---------- semantic gate ----------

def _module_spec_for_crc_braid():
    from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter
    alg = AlgorithmSpec(
        name="crc_word_big",
        display_name="crc_word_big",
        category="checksum",
        description="big-endian braided CRC word step",
        inputs=[Parameter(name="data", rust_type="u64", description="")],
        return_type="u64",
        referenced_standards=["IEEE 802.3", "variant:ieee_reflected"],
    )
    return ModuleSpec(name="crc32", display_name="", description="", algorithms=[alg])


_WRONG_VARIANT_RS = """\
#![forbid(unsafe_code)]
pub const CRC32_TABLE: [u32; 256] = [0u32; 256];

pub fn crc_word_big(mut data: u64) -> u64 {
    for _ in 0..8 {
        let idx = ((data >> 56) & 0xff) as usize;
        data = (data << 8) ^ (CRC32_TABLE[idx] as u64);
    }
    data
}
"""

_RIGHT_VARIANT_RS = _WRONG_VARIANT_RS.replace(
    "(CRC32_TABLE[idx] as u64)", "(CRC32_TABLE[idx] as u64).swap_bytes()"
)


def _write_crate(tmp_path, lib_rs: str):
    (tmp_path / "crc-crate").mkdir()
    (tmp_path / "crc-crate" / "src").mkdir()
    (tmp_path / "crc-crate" / "Cargo.toml").write_text(
        '[package]\nname = "crc-crate"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (tmp_path / "crc-crate" / "src" / "lib.rs").write_text(lib_rs, encoding="utf-8")


def test_semantic_gate_fails_wrong_crc_variant(tmp_path):
    """Negative test: a deliberately-wrong CRC big-endian variant (little
    table entries, no byteswap) must FAIL the semantic gate."""
    _write_crate(tmp_path, _WRONG_VARIANT_RS)
    tester = DifferentialTester(tmp_path, specs=[_module_spec_for_crc_braid()])
    result = tester.gate_semantic()
    assert not result.passed
    assert "crc32_braid_missing_byteswap" in result.stdout


def test_semantic_gate_passes_correct_crc_variant(tmp_path):
    _write_crate(tmp_path, _RIGHT_VARIANT_RS)
    tester = DifferentialTester(tmp_path, specs=[_module_spec_for_crc_braid()])
    result = tester.gate_semantic()
    assert result.passed


def test_semantic_gate_reports_not_run_without_specs(tmp_path):
    tester = DifferentialTester(tmp_path, specs=None)
    result = tester.gate_semantic()
    # Passing here is safe only because the differential gate independently
    # fails closed for unconfigured runs; the summary must say it didn't run.
    assert result.passed
    assert "not run" in result.summary


def test_semantic_gate_fails_when_spec_loading_crashed(tmp_path):
    """A subject that HAS specs whose loading crashed must FAIL the gate —
    infrastructure rot must not silently disarm the wrong-variant defense."""
    tester = DifferentialTester(
        tmp_path, specs=None, specs_error="architecture.json missing",
    )
    result = tester.gate_semantic()
    assert not result.passed
    assert "REFUSING" in result.summary


def test_semantic_gate_fails_on_empty_specs_list(tmp_path):
    tester = DifferentialTester(tmp_path, specs=[])
    result = tester.gate_semantic()
    assert not result.passed
    assert "REFUSING" in result.summary


def test_semantic_gate_survives_bodyless_decl_shadowing(tmp_path):
    """A trait-method declaration before the real fn must not launder the
    wrong-variant source through mis-paired extraction (semantic false-PASS)."""
    lib = (
        "pub trait Tab { fn helper(x: u64) -> u64; }\n"
        "pub const CRC_BIG_TABLE: [u64; 256] = [0u64; 256];\n"
        + _WRONG_VARIANT_RS.replace("#![forbid(unsafe_code)]\n", "")
    )
    _write_crate(tmp_path, lib)
    tester = DifferentialTester(tmp_path, specs=[_module_spec_for_crc_braid()])
    result = tester.gate_semantic()
    assert not result.passed
    assert "crc32_braid_missing_byteswap" in result.stdout


def test_anti_stub_gate_flags_real_zlib_stubs():
    """Integration: run the anti-stub gate against the current zlib output."""
    zlib_root = Path(__file__).parent.parent / "subjects" / "zlib" / ".alchemist" / "output"
    if not zlib_root.exists():
        pytest.skip("zlib output not generated")
    tester = DifferentialTester(zlib_root)
    result = tester.gate_anti_stub()
    assert not result.passed, "Expected stubs in current zlib output"
    assert result.anti_stub_report is not None
    assert len(result.anti_stub_report.violations) >= 18
