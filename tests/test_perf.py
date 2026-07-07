"""Performance parity — verdict logic.

The real cross-language benchmark (checksum: Rust 0.98x C, parity) runs live with
gcc+rustc; here we lock the ratio->verdict classification. (Recording the ratio in
the shipping verifier receipt is a follow-up wiring — see docs/GROUNDING.md.)
"""

from alchemist.reporter.perf import _classify, PerfResult


def test_classify_ratio_verdicts():
    assert _classify(0.98) == "parity"      # essentially the same
    assert _classify(0.80) == "faster"      # meaningfully faster
    assert _classify(1.10) == "parity"      # within 15% -> parity
    assert _classify(1.50) == "regressed"   # 50% slower -> flagged


def test_perf_result_shape():
    r = PerfResult(c_ns=100.0, rust_ns=98.0, ratio=0.98, verdict="parity")
    assert r.ratio == 0.98 and r.verdict == "parity"
