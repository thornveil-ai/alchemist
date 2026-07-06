"""End-to-end auto-onboarding driver: C source -> compiling Rust crate + a
differential oracle + a dependency-ordered fill plan, with NO hand-written setup.

This assembles the pieces (onboard.extract_tables/discover_functions/fill_order +
oracle_gen.classify/harness/signatures) into what `alchemist translate ./lib`
does for the byte-processing function class. The LLM fill itself is driven by the
caller (it needs the model client); this builds everything up to and including
the stubbed crate + the oracle, and hands back the fill order.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from alchemist.autonomy.onboard import (
    extract_tables, discover_functions, fill_order, extract_char_defines,
)
from alchemist.autonomy.oracle_gen import (
    classify_signature, rust_signature, generate_c_harness, rust_call,
)


@dataclass
class OnboardResult:
    crate_dir: Path
    fill_order: list[str]       # every fn to fill, dependency-first
    tested: list[str]           # subset with differential tests (byte-processing)
    skipped: list[str]          # fns the byte-processing oracle can't cover
    num_tables: int
    num_tests: int


def _closure(names, funcs):
    """Transitive call-closure: names + everything they call (that we define)."""
    need = set(names)
    stack = list(names)
    while stack:
        for callee in funcs[stack.pop()].calls:
            if callee in funcs and callee not in need:
                need.add(callee)
                stack.append(callee)
    return need


def build_crate_from_c(c_path: Path, header_name: str, out_dir: Path,
                       crate_name: str, inputs: list[bytes],
                       gcc: str = "g++", gcc_args: tuple = ()) -> OnboardResult:
    c_path, out_dir = Path(c_path), Path(out_dir)
    src = c_path.read_text(encoding="utf-8", errors="replace")
    tables = extract_tables(src)
    funcs = discover_functions(src)
    specs = {n: classify_signature(f) for n, f in funcs.items()}
    order = fill_order(funcs)

    tested = [n for n in order if specs[n].supported]
    # stub the whole call-closure of the tested set (helpers included), in order
    needed = _closure(tested, funcs)
    fill_seq = [n for n in order if n in needed]
    skipped = [n for n in order if n not in needed]

    # --- differential oracle: compile a dispatch harness against the real C ---
    out_dir.mkdir(parents=True, exist_ok=True)
    harness = generate_c_harness([specs[n] for n in tested], header_name)
    (out_dir/"_oracle.cpp").write_text(harness)
    oracle_bin = out_dir/"_oracle"
    subprocess.run([gcc, "-O2", "-I", str(c_path.parent), *gcc_args,
                    "-o", str(oracle_bin), str(out_dir/"_oracle.cpp"), str(c_path)],
                   check=True)

    def run_oracle_scalar(fn: str, inp: bytes) -> int:
        r = subprocess.run([str(oracle_bin), fn], input=inp, capture_output=True)
        return int(r.stdout or b"0")

    def run_oracle_bytes(fn: str, inp: bytes) -> bytes:
        r = subprocess.run([str(oracle_bin), fn], input=inp, capture_output=True)
        return r.stdout

    # --- Rust crate skeleton: tables (data) + stubs (for the model) + tests ---
    crate = out_dir/crate_name
    (crate/"src").mkdir(parents=True, exist_ok=True)
    (crate/"Cargo.toml").write_text(
        '[package]\nname="%s"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n'
        % crate_name)
    tables_rs = "\n".join(t.rust_const() for t in tables.values())
    consts_rs = "\n".join("pub const %s: u8 = %d;" % (n.upper(), v)
                          for n, v in extract_char_defines(src).items())
    stubs = "\n".join("%s { unimplemented!() }" % rust_signature(specs[n]) for n in fill_seq)
    tests, ntests = [], 0
    for n in tested:
        for i, inp in enumerate(inputs):
            if specs[n].buffer_output:
                exp = run_oracle_bytes(n, inp)
                expected = "&[" + ", ".join(str(b) for b in exp) + "]"
                tests.append("    #[test]\n    fn t_%s_%d(){ assert_eq!(%s.as_slice(), %s); }"
                             % (n, i, rust_call(specs[n], inp), expected))
            else:
                exp = run_oracle_scalar(n, inp)
                tests.append("    #[test]\n    fn t_%s_%d(){ assert_eq!(%s, %d); }"
                             % (n, i, rust_call(specs[n], inp), exp))
            ntests += 1
    (crate/"src"/"lib.rs").write_text(
        "#![allow(dead_code, clippy::needless_range_loop, unused_variables)]\n"
        "// Auto-onboarded from %s. Tables provided as data; functions for the model.\n"
        % c_path.name
        + consts_rs + "\n" + tables_rs + "\n\n" + stubs + "\n"
        + "#[cfg(test)]\nmod tests {\n    use super::*;\n" + "\n".join(tests) + "\n}\n")
    return OnboardResult(crate, fill_seq, tested, skipped, len(tables), ntests)
