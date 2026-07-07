"""Performance parity — the translation must be correct AND safe AND competitive.

A verified, memory-safe Rust port that runs at half the speed of the C is a hard
sell. This micro-benchmarks each verified function against its C original (ns/iter,
both at -O2/-O3 release), computes the ratio, and records it in the receipt so a
regression is a first-class signal, not a surprise found in production.

Rust's bounds checks and ownership usually cost little once optimized; where they
don't, the ratio flags exactly which function to look at.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PerfResult:
    c_ns: float
    rust_ns: float
    ratio: float          # rust / c ; 1.0 == parity, >1 slower
    verdict: str          # "parity" | "faster" | "regressed"


def _classify(ratio: float) -> str:
    if ratio <= 1.15:
        return "faster" if ratio < 0.9 else "parity"
    return "regressed"


def bench_scalar(c_source: str, rust_fn: str, fn: str, iters: int, work: Path,
                 gcc: str = "gcc", rustc: str = "rustc") -> PerfResult | None:
    """Benchmark a buffer->scalar fn: C `fn(d, n)` vs Rust `fn(&d)`, same 256-byte
    input, `iters` reps each, at -O3/release. Returns ns/iter and the ratio."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    cbin, rbin = work / "cbench", work / "rbench"
    (work / "cbench.c").write_text(
        c_source + "\n#include <time.h>\n#include <stdio.h>\n"
        "int main(){ unsigned char d[256]; for(int i=0;i<256;i++) d[i]=(unsigned char)i;\n"
        "  volatile unsigned long sink=0; struct timespec a,b;\n"
        "  clock_gettime(CLOCK_MONOTONIC,&a);\n"
        "  for(long i=0;i<%d;i++) sink += %s(d, 256);\n"
        "  clock_gettime(CLOCK_MONOTONIC,&b);\n"
        "  double ns=((b.tv_sec-a.tv_sec)*1e9+(b.tv_nsec-a.tv_nsec))/%d.0;\n"
        "  printf(\"%%f\\n\", ns); return (int)(sink&1); }\n" % (iters, fn, iters))
    (work / "rbench.rs").write_text(
        rust_fn + "\nfn main(){ let d: Vec<u8> = (0..256u32).map(|x| x as u8).collect();\n"
        "  let mut sink: u64 = 0;\n  let t0 = std::time::Instant::now();\n"
        "  for _ in 0..%d { sink = sink.wrapping_add(%s(&d) as u64); }\n"
        "  let ns = t0.elapsed().as_nanos() as f64 / %d as f64;\n"
        "  println!(\"{}\", ns); std::process::exit((sink & 1) as i32); }\n" % (iters, fn, iters))
    if subprocess.run([gcc, "-O3", str(work / "cbench.c"), "-o", str(cbin)], capture_output=True).returncode:
        return None
    if subprocess.run([rustc, "-O", str(work / "rbench.rs"), "-o", str(rbin)], capture_output=True).returncode:
        return None
    c_ns = float(subprocess.run([str(cbin)], capture_output=True, text=True).stdout.strip() or "0")
    r_ns = float(subprocess.run([str(rbin)], capture_output=True, text=True).stdout.strip() or "0")
    if c_ns <= 0 or r_ns <= 0:
        return None
    ratio = r_ns / c_ns
    return PerfResult(round(c_ns, 2), round(r_ns, 2), round(ratio, 3), _classify(ratio))
