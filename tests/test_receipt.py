"""Tests for alchemist.verifier.receipt — verification receipts."""

from __future__ import annotations

import json
from pathlib import Path

from alchemist.verifier.differential_tester import (
    DifferentialConfig,
    GateResult,
    VerificationReport,
)
from alchemist.verifier.proptest_gen import AlgorithmHarness
from alchemist.verifier.receipt import (
    RECEIPT_SCHEMA,
    build_receipt,
    verify_receipt_integrity,
    write_receipt,
)


def _report(passed: bool = True) -> VerificationReport:
    def g(name):
        return GateResult(name=name, passed=passed, summary=f"{name} summary")
    return VerificationReport(
        compile=g("compile"), anti_stub=g("anti-stub"), no_unsafe=g("no-unsafe"),
        semantic=g("semantic"), test=g("test"), differential=g("differential"),
    )


def _config(tmp_path: Path) -> DifferentialConfig:
    c = tmp_path / "ref.c"
    c.write_text("int f(void) { return 1; }\n", encoding="utf-8")
    return DifferentialConfig(
        c_sources=[c],
        harnesses=[AlgorithmHarness(
            algorithm="adler32", category="checksum",
            rust_call="rust_adler32(&input)", c_call="c_adler32(&input)",
            seed=1, cases=5000, boundary_lengths=[0, 5552],
        )],
        ffi_crate_name="c_ref",
        packages=["zlib-checksum"],
    )


def _evidence(tmp_path: Path) -> dict:
    dll = tmp_path / "c_ref.dll"
    dll.write_bytes(b"not a real dll but hashable")
    return {
        "verify_dir": tmp_path,
        "dll_path": dll,
        "bindings": ["adler32 -> zlib_checksum::adler32_z"],
        "unresolved": [("deflate", "no adapter")],
        "cargo_summary": "test result: ok. 17 passed; 0 failed",
    }


def test_receipt_records_gates_oracle_and_bindings(tmp_path):
    r = build_receipt(
        report=_report(), rust_workspace=tmp_path,
        diff_config=_config(tmp_path), diff_evidence=_evidence(tmp_path),
        specs=None,
    )
    assert r["schema"] == RECEIPT_SCHEMA
    assert r["overall_passed"] is True
    assert {g["gate"] for g in r["gates"]} == {
        "compile", "anti-stub", "no-unsafe", "semantic", "test", "differential"}
    h = r["differential"]["harnesses"][0]
    assert h["algorithm"] == "adler32"
    assert h["cases"] == 5000
    assert h["seed"] == 1
    assert h["boundary_lengths"] == [0, 5552]
    assert h["binding"] == "adler32 -> zlib_checksum::adler32_z"
    # Oracle identity: source + DLL hashes present
    assert r["oracle"]["c_sources"][0]["sha256"]
    assert r["oracle"]["dll"]["sha256"]
    assert r["packages"] == ["zlib-checksum"]
    assert r["differential"]["cargo_summary"].startswith("test result: ok")


def test_receipt_integrity_hash_detects_tamper(tmp_path):
    r = build_receipt(
        report=_report(), rust_workspace=tmp_path,
        diff_config=_config(tmp_path), diff_evidence=_evidence(tmp_path),
    )
    assert verify_receipt_integrity(r)
    r["overall_passed"] = False  # tamper
    assert not verify_receipt_integrity(r)


def test_receipt_hmac_when_key_set(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCHEMIST_RECEIPT_KEY", "test-key")
    r = build_receipt(
        report=_report(), rust_workspace=tmp_path,
        diff_config=_config(tmp_path), diff_evidence=_evidence(tmp_path),
    )
    assert r["integrity"]["hmac_sha256"]
    assert verify_receipt_integrity(r, key="test-key")
    assert not verify_receipt_integrity(r, key="wrong-key")


def test_receipt_unsigned_says_so(tmp_path, monkeypatch):
    monkeypatch.delenv("ALCHEMIST_RECEIPT_KEY", raising=False)
    r = build_receipt(report=_report(False), rust_workspace=tmp_path)
    assert r["integrity"]["hmac_sha256"] is None
    assert "unsigned" in r["integrity"]["note"]
    assert r["overall_passed"] is False


def test_write_receipt_roundtrip(tmp_path):
    r = build_receipt(
        report=_report(), rust_workspace=tmp_path,
        diff_config=_config(tmp_path), diff_evidence=_evidence(tmp_path),
    )
    p = write_receipt(r, tmp_path / "verify_gen" / "receipt.json")
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert verify_receipt_integrity(loaded)
    assert loaded["schema"] == RECEIPT_SCHEMA
