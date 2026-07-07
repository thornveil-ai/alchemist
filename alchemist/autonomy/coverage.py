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
from dataclasses import dataclass
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


@dataclass
class CoverageResult:
    corpus: list[bytes]
    coverage: float
    rounds: int


def _mutate(seed: bytes, rng) -> bytes:
    """One greybox mutation: flip a byte to a boundary value, bit-flip, or resize."""
    b = bytearray(seed) if seed else bytearray(b"\x00")
    op = rng.randrange(4)
    if op == 0:                                   # set a byte to a comparison edge
        b[rng.randrange(len(b))] = rng.choice(BOUNDARY_BYTES)
    elif op == 1:                                 # bit flip
        i = rng.randrange(len(b)); b[i] ^= 1 << rng.randrange(8)
    elif op == 2 and len(b) < 32:                 # grow
        b.append(rng.choice(BOUNDARY_BYTES))
    elif len(b) >= 1:                             # shrink (can reach empty -> n==0 branch)
        del b[rng.randrange(len(b))]
    return bytes(b)


def coverage_guided_inputs(c_source: str, driver_main: str, work: Path,
                           seeds: list[bytes] | None = None, max_rounds: int = 400,
                           plateau: int = 80, gcc: str = "gcc",
                           seed: int = 1234) -> CoverageResult:
    """Greybox loop: keep mutating corpus members; any input that raises CUMULATIVE
    branch coverage joins the corpus. Exploits gcov's accumulating counters (one run
    per candidate, no resets). Stops at 100% or after `plateau` gainless rounds.

    Finds the comparison edges automatically from a trivial seed — the corpus that
    results is the coverage-complete input set the differential should verify against.
    """
    import random
    rng = random.Random(seed)
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    src = work / "cov.c"
    src.write_text(c_source + "\n" + driver_main)
    for f in work.glob("*.gc*"):
        f.unlink()
    if subprocess.run([gcc, "--coverage", "-O0", str(src), "-o", str(work / "cov")],
                      capture_output=True).returncode:
        return CoverageResult([], 0.0, 0)

    def run(inp: bytes):
        subprocess.run([str(work / "cov")], input=inp, capture_output=True, cwd=str(work))

    def cum_cov() -> float:
        g = subprocess.run(["gcov", "-b", "-n", "cov.c"], capture_output=True, text=True, cwd=str(work))
        m = re.search(r"Taken at least once:\s*([\d.]+)%", g.stdout)
        return (float(m.group(1)) / 100.0) if m else 0.0

    corpus: list[bytes] = []
    best = 0.0
    for s in (seeds or [b"", b"\x00"]):
        run(s)
        c = cum_cov()
        if c > best:
            best, corpus = c, corpus + [s]
    stale = 0
    for r in range(max_rounds):
        if best >= 1.0 or stale >= plateau:
            return CoverageResult(corpus, best, r)
        cand = _mutate(rng.choice(corpus) if corpus else b"\x00", rng)
        run(cand)
        c = cum_cov()
        if c > best:                              # this input reached new branches
            best, corpus, stale = c, corpus + [cand], 0
        else:
            stale += 1
    return CoverageResult(corpus, best, max_rounds)
