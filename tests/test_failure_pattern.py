"""Failure-pattern aggregator: the differential feedback must tell the model
WHERE to look, not just that it's wrong. The highest-signal fact for a
byte-exact hash/codec is whether the empty/smallest input already fails."""
from alchemist.implementer.tdd_generator import _distill_vector_divergence, _failure_pattern


def _mk(label, got, want):
    return (
        f"thread 't' panicked at x.rs:1:1:\n"
        f"assertion `left == right` failed: {label}\n"
        f"  left: {got}\n right: {want}\n"
    )


def test_empty_input_failure_points_at_init():
    out = _mk("fuzz_input_len_0", "[124, 78, 94, 59]", "[49, 14, 14, 221]") + \
        _mk("fuzz_input_len_16", "[1, 2, 3, 4]", "[200, 100, 50, 25]")
    p = _failure_pattern(out)
    assert "across 2 failing vectors" in p
    assert "EMPTY" in p and "INITIALIZATION" in p
    # and it is prepended to the detailed distillation
    full = _distill_vector_divergence(out)
    assert full.startswith("## Failure pattern")
    assert "First divergence at OUTPUT byte index" in full


def test_nonempty_smallest_reports_length():
    out = _mk("fuzz_input_len_8", "[1, 2, 3]", "[9, 2, 3]") + \
        _mk("fuzz_input_len_24", "[4, 5, 6]", "[4, 5, 9]")
    p = _failure_pattern(out)
    assert "smallest failing input is 8 byte(s)" in p
    # divergence indices differ (0 vs 2) => no "every output diverges at byte 0"
    assert "EVERY output diverges at byte 0" not in p


def test_single_failure_no_pattern():
    # <2 failing vectors => aggregator stays silent (no false signal)
    out = _mk("fuzz_input_len_0", "[1, 2]", "[3, 4]")
    assert _failure_pattern(out) == ""


def test_no_asserts_empty():
    assert _failure_pattern("no left/right here") == ""
    assert _distill_vector_divergence("nothing") == ""
