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
