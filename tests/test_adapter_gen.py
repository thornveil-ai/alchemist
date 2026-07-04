"""Tests for alchemist.verifier.adapter_gen — the differential adapter emitter."""

from __future__ import annotations

import re
from pathlib import Path

from alchemist.verifier.adapter_gen import (
    AdapterPlan,
    discover_rust_api,
    emit_adapter_lib,
    emit_unresolved_tests,
    plan_adapters,
)
from alchemist.verifier.proptest_gen import AlgorithmHarness


def _write_crate(root: Path, pkg: str, lib_rs: str) -> None:
    d = root / pkg
    (d / "src").mkdir(parents=True)
    (d / "Cargo.toml").write_text(
        f'[package]\nname = "{pkg}"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (d / "src" / "lib.rs").write_text(lib_rs, encoding="utf-8")


_CHECKSUM_LIB = """\
#![forbid(unsafe_code)]
pub fn adler32_z(adler: u32, buf: &[u8], len: usize) -> u32 { adler + len as u32 + buf.len() as u32 }
pub fn crc32(crc: u32, buf: &[u8], len: usize) -> u32 { crc ^ len as u32 ^ buf.len() as u32 }
#[cfg(test)]
mod tests {
    pub fn not_api(x: u32) -> u32 { x }
}
"""


def _checksum_harness(algo: str, seed: int) -> AlgorithmHarness:
    return AlgorithmHarness(
        algorithm=algo,
        category="checksum",
        rust_call=f"rust_{algo}(&input)",
        c_call=f"c_{algo}(&input)",
        seed=seed,
    )


# ---------- discovery ----------

def test_discover_finds_pub_fns_and_skips_test_modules(tmp_path):
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    api = discover_rust_api(tmp_path)
    assert "adler32_z" in api and "crc32" in api
    assert api["crc32"][0].crate == "zlib-checksum"
    assert api["crc32"][0].ret == "u32"
    assert "not_api" not in api  # inside #[cfg(test)]


def test_discover_records_every_defining_crate(tmp_path):
    _write_crate(tmp_path, "aaa-compat", "pub fn crc32(crc: u32, buf: &[u8], len: usize) -> u32 { 0 }\n")
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    api = discover_rust_api(tmp_path)
    assert {d.crate for d in api["crc32"]} == {"aaa-compat", "zlib-checksum"}


def test_discover_packages_scoping_excludes_other_crates(tmp_path):
    _write_crate(tmp_path, "aaa-compat", "pub fn crc32(crc: u32, buf: &[u8], len: usize) -> u32 { 0 }\n")
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    api = discover_rust_api(tmp_path, packages=["zlib-checksum"])
    assert {d.crate for d in api["crc32"]} == {"zlib-checksum"}


# ---------- resolution ----------

def test_plan_resolves_checksum_against_real_signatures(tmp_path):
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    plan = plan_adapters(
        [_checksum_harness("adler32", 1), _checksum_harness("crc32", 0)],
        rust_workspace=tmp_path,
        ffi_crate_name="c_ref",
        c_fn_names={"adler32", "crc32"},
    )
    assert not plan.unresolved
    bodies = "\n".join(r.rust_wrapper for r in plan.resolved)
    # adler32 has no exact match — must fall through to adler32_z
    assert "zlib_checksum::adler32_z(1u32, data, data.len())" in bodies
    assert "zlib_checksum::crc32(0u32, data, data.len())" in bodies
    assert plan.rust_crates == {"zlib-checksum"}
    assert any("adler32 -> zlib_checksum::adler32_z" == r.resolution
               for r in plan.resolved)


def test_ambiguous_symbol_refused_not_silently_bound(tmp_path):
    """A shadowing crate must NOT silently win the binding — that would
    differentially verify code that never ships."""
    _write_crate(tmp_path, "aaa-compat", "pub fn crc32(crc: u32, buf: &[u8], len: usize) -> u32 { 0 }\n")
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    plan = plan_adapters(
        [_checksum_harness("crc32", 0)],
        rust_workspace=tmp_path,
        ffi_crate_name="c_ref",
        c_fn_names={"crc32"},
    )
    assert not plan.resolved
    assert plan.unresolved
    assert "multiple crates" in plan.unresolved[0][1]


_COMPRESSION_LIB = """\
#![forbid(unsafe_code)]
pub struct CompressionError;
pub struct DecompressionError;
pub fn compress_z(dest: &mut [u8], dest_len: &mut usize, source: &[u8], source_len: usize) -> Result<(), CompressionError> {
    let _ = (dest, dest_len, source, source_len); Ok(())
}
pub fn uncompress(dest: &mut [u8], dest_len: &mut usize, source: &[u8], source_len: usize) -> Result<(), DecompressionError> {
    let _ = (dest, dest_len, source, source_len); Ok(())
}
"""


def _deflate_harness() -> AlgorithmHarness:
    return AlgorithmHarness(
        algorithm="deflate", category="compression",
        rust_call="rust_compress(&input)",
        c_call="c_compress(&input)",
        rust_decompress_call="rust_uncompress(&compressed, input.len() + 64)",
        c_decompress_call="c_uncompress(&compressed, input.len() + 64)",
    )


def test_compression_resolves_full_footprint_wrappers(tmp_path):
    _write_crate(tmp_path, "zlib-compression", _COMPRESSION_LIB)
    plan = plan_adapters(
        [_deflate_harness()], rust_workspace=tmp_path, ffi_crate_name="c_zlib_ref",
        c_fn_names={"compress", "uncompress"},
    )
    assert not plan.unresolved, plan.unresolved
    r = plan.resolved[0]
    # Rust side: footprint tuples, status mapped, buffer truncated
    assert "pub fn rust_compress(data: &[u8]) -> (i32, Vec<u8>)" in r.rust_wrapper
    assert "pub fn rust_uncompress(data: &[u8], cap: usize) -> (i32, Vec<u8>)" in r.rust_wrapper
    assert "zlib_compression::compress_z(&mut dest, &mut dest_len, data, data.len())" in r.rust_wrapper
    assert "dest.truncate(dest_len);" in r.rust_wrapper
    # C side: no asserts inside wrappers — status is RETURNED, not swallowed
    assert "pub fn c_compress(data: &[u8]) -> (i32, Vec<u8>)" in r.c_wrapper
    assert "pub fn c_uncompress(data: &[u8], cap: usize) -> (i32, Vec<u8>)" in r.c_wrapper
    assert "assert" not in r.c_wrapper
    assert "(rc as i32, dest)" in r.c_wrapper
    assert "compress_z" in r.resolution and "uncompress" in r.resolution


def test_compression_without_rust_impl_lands_in_unresolved(tmp_path):
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)  # no compression fns
    plan = plan_adapters(
        [_deflate_harness()], rust_workspace=tmp_path, ffi_crate_name="c_ref",
        c_fn_names={"compress", "uncompress"},
    )
    assert not plan.resolved
    assert plan.unresolved and plan.unresolved[0][0].algorithm == "deflate"
    assert "not found" in plan.unresolved[0][1]


def test_unadaptable_category_lands_in_unresolved(tmp_path):
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    h = AlgorithmHarness(
        algorithm="kalman", category="filter",
        rust_call="rust_kalman(&input)", c_call="c_kalman(&input)",
    )
    plan = plan_adapters(
        [h], rust_workspace=tmp_path, ffi_crate_name="c_ref",
        c_fn_names={"kalman"},
    )
    assert not plan.resolved
    assert plan.unresolved and "no adapter template" in plan.unresolved[0][1]


# ---------- emission ----------

def test_emit_unresolved_tests_is_single_string_literal():
    """Rust does NOT concatenate adjacent string literals — the failing test
    must be one literal or it is a rustc parse error that hides every
    resolvable harness in the same file."""
    plan = AdapterPlan()
    plan.unresolved.append((
        _checksum_harness("deflate", 0),
        "no adapter template for category 'compression'",
    ))
    src = emit_unresolved_tests(plan)
    m = re.search(r"panic!\((.*)\);", src, re.DOTALL)
    assert m, src
    arg = m.group(1).strip()
    # Exactly one string literal: starts and ends with a quote, no interior
    # unescaped quote (we replace embedded double-quotes with single quotes).
    assert arg.startswith('"') and arg.endswith('"')
    assert '"' not in arg[1:-1], f"adjacent literals detected: {arg}"


def test_emit_unresolved_tests_escapes_braces_for_format_string():
    plan = AdapterPlan()
    plan.unresolved.append((
        _checksum_harness("weird", 0),
        "signature (Foo { x: u32 }) has no adapter",
    ))
    src = emit_unresolved_tests(plan)
    assert "{{ x: u32 }}" in src
    assert "{ x: u32 }" not in src.replace("{{ x: u32 }}", "")


def test_emit_adapter_lib_contains_both_sides(tmp_path):
    _write_crate(tmp_path, "zlib-checksum", _CHECKSUM_LIB)
    plan = plan_adapters(
        [_checksum_harness("crc32", 0)],
        rust_workspace=tmp_path, ffi_crate_name="c_zlib_ref",
        c_fn_names={"crc32"},
    )
    lib = emit_adapter_lib(plan, ffi_crate_name="c_zlib_ref")
    assert "pub fn c_crc32(data: &[u8]) -> u32" in lib
    assert "pub fn rust_crc32(data: &[u8]) -> u32" in lib
    assert "c_zlib_ref::crc32(0 as _" in lib
