"""Pillar 3 — incremental verified FFI migration.

A big-bang auto-rewrite of a whole codebase is un-trustable; 500 individually-
verified function swaps are. This emits, for a verified safe-Rust function, a thin
`#[no_mangle] pub extern "C"` wrapper that presents the ORIGINAL C ABI (raw ptr +
len) on the outside and calls the safe core on the inside. Linked into the C
program in place of the C original, the whole program can be re-run / re-fuzzed and
differential-checked byte-for-byte before the swap is committed.

Raw pointers appear only in the wrapper (one `from_raw_parts`); all real logic stays
in safe Rust. Migrate one leaf at a time, verify the program is unchanged, advance.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


def emit_c_abi_export(c_name: str, kind: str = "scalar", ret_rust: str = "u32",
                      safe_fn: str | None = None) -> str:
    """extern "C" wrapper bridging the C ABI to a verified safe-Rust core.

    kind="scalar":  C `f(const u8*, size_t) -> RET`  -> safe `f_safe(&[u8]) -> RET`
    kind="buffer":  C `f(const u8*, size_t, u8* out) -> len` -> safe `f_safe(&[u8]) -> Vec<u8>`
    """
    safe_fn = safe_fn or (c_name + "_safe")
    if kind == "buffer":
        return (
            '#[no_mangle]\n'
            'pub extern "C" fn %s(data: *const u8, len: usize, out: *mut u8) -> usize {\n'
            '    let __s = unsafe { core::slice::from_raw_parts(data, len) };\n'
            '    let __r = %s(__s);\n'
            '    unsafe { core::ptr::copy_nonoverlapping(__r.as_ptr(), out, __r.len()); }\n'
            '    __r.len()\n}\n' % (c_name, safe_fn))
    return (
        '#[no_mangle]\n'
        'pub extern "C" fn %s(data: *const u8, len: usize) -> %s {\n'
        '    let __s = unsafe { core::slice::from_raw_parts(data, len) };\n'
        '    %s(__s)\n}\n' % (c_name, ret_rust, safe_fn))


def emit_migration_shim(c_name: str, kind: str, ret_rust: str, safe_body: str,
                        safe_fn: str | None = None) -> str:
    """Full staticlib source: the verified safe core + its C-ABI export. Compile
    with `--crate-type=staticlib` and link into the C program in place of `c_name`."""
    safe_fn = safe_fn or (c_name + "_safe")
    return (
        "#![allow(dead_code)]\n"
        + safe_body.rstrip() + "\n\n"
        + emit_c_abi_export(c_name, kind, ret_rust, safe_fn))


def strip_c_function(src: str, fn: str) -> str:
    """Remove a function's DEFINITION (not its prototype) from C source, so the Rust
    replacement provides the symbol at link time."""
    m = re.search(r"(^|[};])\s*([A-Za-z_][\w \t\*]*?\b" + re.escape(fn) + r"\s*\([^;{]*\)\s*)\{",
                  src, re.M)
    if not m:
        return src
    brace = src.index("{", m.start())
    depth = 0
    for j in range(brace, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                start = m.start(2)
                return src[:start] + src[j + 1:]
    return src


@dataclass
class MigrationResult:
    verified: bool
    checked: int
    first_mismatch: bytes | None


def migrate_function(c_files: list[Path], target_fn: str, shim_rs: str, inputs: list[bytes],
                     work: Path, gcc: str = "gcc", rustc: str = "rustc") -> MigrationResult:
    """Whole-program verified swap: build the all-C program and a version with
    `target_fn`'s C definition stripped and the verified Rust shim linked in its
    place; run BOTH on every input and require byte-identical stdout. Verified ->
    the swap is safe to commit; not verified -> revert.
    """
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    c_files = [Path(f) for f in c_files]

    # all-C reference binary
    ref = work / "prog_allc"
    if subprocess.run([gcc, "-O2", *[str(f) for f in c_files], "-o", str(ref)],
                      capture_output=True).returncode:
        return MigrationResult(False, 0, None)

    # FFI binary: strip target_fn's C def, link the Rust shim in its place
    (work / "shim.rs").write_text(shim_rs)
    if subprocess.run([rustc, "-O", "--crate-type=staticlib", str(work / "shim.rs"),
                       "-o", str(work / "libshim.a")], capture_output=True).returncode:
        return MigrationResult(False, 0, None)
    stripped = []
    for f in c_files:
        txt = f.read_text()
        if target_fn in txt and re.search(r"\b" + re.escape(target_fn) + r"\s*\([^;]*\)\s*\{", txt):
            p = work / ("stripped_" + f.name)
            p.write_text(strip_c_function(txt, target_fn))
            stripped.append(p)
        else:
            stripped.append(f)
    ffi = work / "prog_ffi"
    if subprocess.run([gcc, "-O2", *[str(f) for f in stripped], str(work / "libshim.a"),
                       "-o", str(ffi), "-lpthread", "-ldl"], capture_output=True).returncode:
        return MigrationResult(False, 0, None)

    for inp in inputs:
        a = subprocess.run([str(ref)], input=inp, capture_output=True).stdout
        b = subprocess.run([str(ffi)], input=inp, capture_output=True).stdout
        if a != b:
            return MigrationResult(False, len(inputs), inp)
    return MigrationResult(True, len(inputs), None)
