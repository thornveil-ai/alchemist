"""Pillar 4 — coverage-driven differential: boundary-aware input generation.

The gcov measurement (naive 20% vs boundary-aware 100% branch coverage on a branchy
fn) is proven on the box; here we lock the deterministic generator.
"""

from alchemist.autonomy.coverage import boundary_inputs, BOUNDARY_BYTES


def test_boundary_inputs_hit_comparison_edges():
    inps = boundary_inputs()
    singles = {i[0] for i in inps if len(i) == 1}
    # the edges real C branches on must each appear as a probe
    for v in (0x00, 0x7F, 0x80, 0xC0, 0xE0, 0xF0, 0xFF):
        assert v in singles, f"missing boundary probe 0x{v:02x}"


def test_boundary_inputs_include_empty_for_zero_length_branch():
    assert b"" in boundary_inputs()   # exercises the `n == 0` branch


def test_boundary_inputs_deterministic():
    assert boundary_inputs() == boundary_inputs()   # no RNG -> reproducible receipts
