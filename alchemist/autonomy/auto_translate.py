"""End-to-end auto-onboarding driver: C source(s) -> compiling Rust crate + a
differential oracle + a dependency-ordered fill plan, with NO hand-written setup.

Assembles onboard (tables/functions/order) + oracle_gen (classify/harness/sigs) +
build_discovery (how to compile) into what `alchemist translate ./lib` does for
the byte-processing + output-buffer function classes. Handles a single file or a
WHOLE DIRECTORY of C (Tier 1 #2): tables/functions merged across files, the call
graph recomputed across the union, one oracle compiled from all sources.
"""

from __future__ import annotations

import subprocess
import re
from dataclasses import dataclass, field
from pathlib import Path

from alchemist.autonomy.onboard import (
    extract_tables, discover_functions, fill_order, extract_char_defines, CFunc,
)
from alchemist.autonomy.oracle_gen import (
    classify_signature, rust_signature, generate_c_harness, rust_call,
)
from alchemist.autonomy.build_discovery import discover_build


@dataclass
class OnboardResult:
    crate_dir: Path
    fill_order: list[str]
    tested: list[str]
    skipped: list[str]
    num_tables: int
    num_tests: int
    sources: list[Path] = field(default_factory=list)
    stubbed: list[str] = field(default_factory=list)


def _is_static(f: CFunc) -> bool:
    return f.ret.split()[:1] == ["static"] if f.ret else False


def _closure(names, funcs):
    need = set(names)
    stack = list(names)
    while stack:
        for callee in funcs[stack.pop()].calls:
            if callee in funcs and callee not in need:
                need.add(callee)
                stack.append(callee)
    return need


def _c_sources(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(p.rglob("*.c")) + sorted(p.rglob("*.cpp"))
        else:
            out.append(p)
    return out


def build_crate_from_sources(paths: list[Path], out_dir: Path, crate_name: str,
                             inputs: list[bytes], search_roots: list[Path] | None = None,
                             gcc: str = "g++") -> OnboardResult:
    sources = _c_sources([Path(p) for p in paths])
    out_dir = Path(out_dir)
    search_roots = [Path(r) for r in (search_roots or [])] or \
        list(dict.fromkeys(s.parent for s in sources))

    # --- merge onboarding across every source file ---
    tables, funcs, char_defs = {}, {}, {}
    for s in sources:
        txt = s.read_text(encoding="utf-8", errors="replace")
        tables.update(extract_tables(txt))
        funcs.update(discover_functions(txt))
        char_defs.update(extract_char_defines(txt))
    # recompute the call graph across the UNION of function names (cross-file)
    names = set(funcs)
    for f in funcs.values():
        f.calls = {c for c in re.findall(r"\b(\w+)\s*\(", f.body)
                   if c in names and c != f.name}

    specs = {n: classify_signature(f) for n, f in funcs.items()}
    order = fill_order(funcs)
    # only NON-static, cleanly-classified fns are oracle-testable (harness is a
    # separate translation unit — it can't call `static` functions)
    tested = [n for n in order if specs[n].supported and not _is_static(funcs[n])]
    needed = _closure(tested, funcs)
    fill_seq = [n for n in order if n in needed]
    skipped = [n for n in order if n not in needed]

    # --- discover how to compile, then build the differential oracle ---
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = discover_build(sources, search_roots, out_dir, gcc=gcc)
    headers = sorted({h.name for s in sources for h in s.parent.glob("*.h")})
    harness = generate_c_harness([specs[n] for n in tested], headers)
    (out_dir / "_oracle.cpp").write_text(harness)
    oracle_bin = out_dir / "_oracle"
    subprocess.run(plan.compile_cmd([out_dir / "_oracle.cpp"], oracle_bin),
                   check=True)

    def run_scalar(fn, inp):
        return int(subprocess.run([str(oracle_bin), fn], input=inp,
                                  capture_output=True).stdout or b"0")

    def run_bytes(fn, inp):
        return subprocess.run([str(oracle_bin), fn], input=inp,
                              capture_output=True).stdout

    # --- Rust crate: consts + tables (data) + coherent stubs + differential tests ---
    all_src = "\n".join(s.read_text(encoding="utf-8", errors="replace") for s in sources)
    crate = out_dir / crate_name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="%s"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n'
        % crate_name)
    consts_rs = "\n".join("pub const %s: u8 = %d;" % (n.upper(), v)
                          for n, v in char_defs.items())
    tables_rs = "\n".join(t.rust_const() for t in tables.values())
    stubs = "\n".join("%s { unimplemented!() }" % rust_signature(specs[n]) for n in fill_seq)
    tests, ntests = [], 0
    for n in tested:
        for i, inp in enumerate(inputs):
            if specs[n].buffer_output:
                exp = "&[" + ", ".join(str(b) for b in run_bytes(n, inp)) + "]"
                tests.append("    #[test]\n    fn t_%s_%d(){ assert_eq!(%s.as_slice(), %s); }"
                             % (n, i, rust_call(specs[n], inp), exp))
            else:
                tests.append("    #[test]\n    fn t_%s_%d(){ assert_eq!(%s, %d); }"
                             % (n, i, rust_call(specs[n], inp), run_scalar(n, inp)))
            ntests += 1
    (crate / "src" / "lib.rs").write_text(
        "#![allow(dead_code, clippy::needless_range_loop, unused_variables)]\n"
        "// Auto-onboarded from %d source file(s). Tables/consts are data; functions for the model.\n"
        % len(sources)
        + consts_rs + "\n" + tables_rs + "\n\n" + stubs + "\n"
        + "#[cfg(test)]\nmod tests {\n    use super::*;\n" + "\n".join(tests) + "\n}\n")
    return OnboardResult(crate, fill_seq, tested, skipped, len(tables), ntests,
                         sources=sources, stubbed=plan.stubbed)


def build_crate_from_c(c_path: Path, header_name: str, out_dir: Path,
                       crate_name: str, inputs: list[bytes],
                       gcc: str = "g++", gcc_args: tuple = ()) -> OnboardResult:
    """Single-file convenience wrapper (kept for existing callers/tests)."""
    return build_crate_from_sources([Path(c_path)], out_dir, crate_name, inputs,
                                    search_roots=[Path(c_path).parent], gcc=gcc)
