"""Item 3 — sanitizer-diff: raise 'verified' toward proof.

Differential equivalence says the Rust matches the C. But the C may itself contain
LATENT undefined behavior (signed overflow, OOB read/write, use-after-free) that
only fires on some inputs — and a faithful translation must NOT reproduce it; the
safe Rust must instead be well-defined. This compiles the C under ASan+UBSan and
runs it on the (ideally coverage-complete) differential inputs, surfacing exactly
which UB classes the C exhibits.

Pairs with coverage_guided_inputs: drive inputs until every branch is covered, then
sanitizer-check that set — so 'no UB found' is a claim over the reachable behavior,
not a lucky sample. Each finding is a concrete bug the Rust port eliminated.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


_UB = re.compile(r"runtime error:\s*(.+?)\s*$|ERROR:\s*AddressSanitizer:\s*(\S+)")


def sanitizer_check(c_source: str, driver_main: str, inputs: list[bytes], work: Path,
                    gcc: str = "gcc") -> list[str]:
    """Compile `c_source`+`driver_main` under ASan+UBSan, run every input, return the
    distinct UB/memory-error classes observed (empty list = clean over these inputs)."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    src = work / "san.c"
    src.write_text(c_source + "\n" + driver_main)
    if subprocess.run([gcc, "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                       "-g", "-O0", str(src), "-o", str(work / "san")],
                      capture_output=True).returncode:
        return ["<compile failed under sanitizers>"]
    env = {**os.environ, "UBSAN_OPTIONS": "print_stacktrace=0",
           "ASAN_OPTIONS": "detect_leaks=1"}
    findings: set[str] = set()
    for inp in inputs:
        r = subprocess.run([str(work / "san")], input=inp, capture_output=True, env=env)
        for line in r.stderr.decode(errors="replace").splitlines():
            m = _UB.search(line)
            if m:
                findings.add((m.group(1) or m.group(2)).strip())
    return sorted(findings)
