"""Performance parity — verdict logic + receipt field.

The real cross-language benchmark (checksum: Rust 0.98x C, parity) is proven on the
box with gcc+rustc; here we lock the ratio->verdict classification and the receipt
carrying the perf ratio.
"""

from alchemist.autonomy.perf import _classify, PerfResult
from alchemist.autonomy.provenance import VerificationReceipt, SafetyReport


def test_classify_ratio_verdicts():
    assert _classify(0.98) == "parity"      # essentially the same
    assert _classify(0.80) == "faster"      # meaningfully faster
    assert _classify(1.10) == "parity"      # within 15% -> parity
    assert _classify(1.50) == "regressed"   # 50% slower -> flagged


def test_perf_result_shape():
    r = PerfResult(c_ns=100.0, rust_ns=98.0, ratio=0.98, verdict="parity")
    assert r.ratio == 0.98 and r.verdict == "parity"


def test_receipt_carries_perf_ratio():
    r = VerificationReceipt("f", "verified", 40, 1.0, SafetyReport(0, 0, 0, True),
                            True, [], "gemma-4-31b", perf_ratio=0.98)
    assert r.perf_ratio == 0.98
    assert "perf_ratio" in r.canonical()    # part of the signed content
    # default None keeps older receipts valid
    r2 = VerificationReceipt("g", "verified", 1, 1.0, SafetyReport(0, 0, 0, True), None, [], "m")
    assert r2.perf_ratio is None
