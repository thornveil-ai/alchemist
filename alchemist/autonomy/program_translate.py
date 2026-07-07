"""Pillar 2 top-tier — the whole-program translator.

Composes the whole-program type model (Pillar 2) with the FFI migration harness
(Pillar 3): ingest a multi-function C program, translate every function BOTTOM-UP
(leaves first, so each caller sees its already-translated callees with consistent
signatures from the shared type model), then verify the WHOLE program by linking the
Rust in place of the C entry point and requiring byte-identical output.

The point: per-function translation is not enough for a codebase — signatures must
agree at every call boundary and the composed program must behave identically. This
proves both at once.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from alchemist.autonomy.onboard import discover_functions, c_to_rust_scalar
from alchemist.autonomy.type_model import ProgramTypeModel
from alchemist.autonomy.ffi_migrate import migrate_function, emit_c_abi_export


@dataclass
class ProgramResult:
    order: list[str]          # bottom-up translation order
    verified: bool
    checked: int


def _rust_sig(fn, funcs, tm: ProgramTypeModel) -> tuple[str, str, str]:
    """(safe signature, kind, rust return) for a function, from the shared type model.
    A (const byte*, len) pair -> &[u8]; scalar params map straight through."""
    params = [p.strip() for p in funcs[fn].params.split(",") if p.strip() and p.strip() != "void"]
    ret = tm.rust_type(funcs[fn].ret) if funcs[fn].ret.strip() != "void" else "()"
    is_buf = (len(params) == 2 and ("*" in params[0] or "[" in params[0])
              and re.search(r"\b(len|n|size|count)\b", params[1]))
    if is_buf:
        return ("pub fn %s(data: &[u8]) -> %s" % (fn, ret), "buffer", ret)
    args = []
    for p in params:
        nm = p.split()[-1].lstrip("*")
        args.append("%s: %s" % (nm, tm.rust_type(" ".join(p.split()[:-1]))))
    return ("pub fn %s(%s) -> %s" % (fn, ", ".join(args), ret), "scalar", ret)


def translate_program(c_files: list[Path], entry_fn: str, inputs: list[bytes], work: Path,
                      fill, gcc: str = "gcc", rustc: str = "rustc") -> ProgramResult:
    """Bottom-up translate a multi-function C program, verify whole-program via FFI.

    `fill(fn, signature, c_body, module_so_far) -> rust_fn_text` produces one safe-Rust
    function (the model, or a stub in tests). Functions are filled leaves-first so a
    caller's fill can rely on its callees already existing with stable signatures.
    """
    c_files = [Path(f) for f in c_files]
    srcs = [f.read_text() for f in c_files]
    funcs = {}
    for s in srcs:
        funcs.update(discover_functions(s))
    tm = ProgramTypeModel.from_sources(srcs)
    # `main` (and test drivers) stay in C — we translate the LIBRARY functions and
    # verify through the untouched C entry point calling the migrated code.
    order = [n for n in tm.topo_order(funcs) if n in funcs and n != "main"]

    module = "#![allow(dead_code, unused_variables, non_snake_case)]\n"
    sigs = {}
    for fn in order:
        sig, kind, ret = _rust_sig(fn, funcs, tm)
        sigs[fn] = (sig, kind, ret)
        rust_fn = fill(fn, sig, funcs[fn].body, module)
        module += "\n" + rust_fn.rstrip() + "\n"

    # Add a C-ABI export owning the entry's C name so it links in place of the C
    # original; rename the safe entry to *_impl so the names don't collide. The
    # transitive safe callees (already in `module`) ride along unchanged.
    _, kind, ret = sigs[entry_fn]
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    renamed = re.sub(r"\b" + re.escape(entry_fn) + r"\b", entry_fn + "_impl", module)
    if kind == "buffer":
        export = ('#[no_mangle]\npub extern "C" fn %s(data: *const u8, len: usize) -> %s {\n'
                  '    let s = unsafe { core::slice::from_raw_parts(data, len) };\n    %s_impl(s)\n}\n'
                  % (entry_fn, ret, entry_fn))
    else:  # scalar entry: forward each scalar arg straight through
        params = [p.strip() for p in funcs[entry_fn].params.split(",") if p.strip() and p != "void"]
        names = [p.split()[-1].lstrip("*") for p in params]
        c_par = ", ".join("%s: %s" % (n, c_to_rust_scalar(" ".join(p.split()[:-1])))
                          for p, n in zip(params, names))
        export = ('#[no_mangle]\npub extern "C" fn %s(%s) -> %s {\n    %s_impl(%s)\n}\n'
                  % (entry_fn, c_par, ret, entry_fn, ", ".join(names)))
    shim_rs = renamed + "\n" + export
    (work / "prog.rs").write_text(shim_rs)
    res = migrate_function(c_files, entry_fn, shim_rs, inputs, work / "verify", gcc=gcc, rustc=rustc)
    return ProgramResult(order, res.verified, res.checked)
