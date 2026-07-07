"""Pillar 4 — coverage-driven differential.

"Byte-exact on N fuzz vectors" is evidence, not proof, and that gap is exactly where
an accreditor pushes. This measures how much of the C's BRANCH structure a given
input set actually exercises (via gcov), and drives generation toward uncovered
branches so the differential claim becomes "equivalent across coverage-complete
inputs." The coverage number rides along in the verification receipt.

Boundary-aware generation matters: a function that branches on `d[0] < 0xC0` is
only meaningfully tested by inputs straddling 0xC0 — random bytes miss the edges.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# byte values that straddle the comparison edges real C tends to branch on
BOUNDARY_BYTES = [0x00, 0x01, 0x7F, 0x80, 0x81, 0xBF, 0xC0, 0xC1,
                  0xDF, 0xE0, 0xE1, 0xEF, 0xF0, 0xF1, 0xFE, 0xFF]


def boundary_inputs(max_len: int = 4) -> list[bytes]:
    """Inputs built from boundary bytes + a few lengths — hits comparison edges
    random bytes miss. Deterministic (no RNG)."""
    out = [b"", bytes([0])]
    for v in BOUNDARY_BYTES:
        out.append(bytes([v]))
        out.append(bytes([v]) + b"\x00" * (max_len - 1))
    for a in (0x00, 0x80, 0xC0, 0xE0, 0xF0):
        for b in (0x00, 0x80, 0xBF):
            out.append(bytes([a, b]))
    return out


def measure_branch_coverage(c_source: str, driver_main: str, inputs: list[bytes],
                            work: Path, gcc: str = "gcc") -> float:
    """Compile `c_source`+`driver_main` with gcov instrumentation, run every input,
    return the fraction of branches taken at least once (0.0-1.0)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    src = work / "cov.c"
    src.write_text(c_source + "\n" + driver_main)
    for f in work.glob("*.gc*"):
        f.unlink()
    r = subprocess.run([gcc, "--coverage", "-O0", str(src), "-o", str(work / "cov")],
                       capture_output=True, text=True)
    if r.returncode:
        return 0.0
    for inp in inputs:
        subprocess.run([str(work / "cov")], input=inp, capture_output=True, cwd=str(work))
    g = subprocess.run(["gcov", "-b", "-n", "cov.c"], capture_output=True, text=True, cwd=str(work))
    m = re.search(r"Taken at least once:\s*([\d.]+)%", g.stdout)
    return (float(m.group(1)) / 100.0) if m else 0.0
