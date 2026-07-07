"""Pillar 3 — FFI migration wrapper generation.

The end-to-end (generated wrapper links into the C program, byte-identical output)
is proven on the box with gcc+rustc; here we lock the emitted structure.
"""

from alchemist.autonomy.ffi_migrate import (
    emit_c_abi_export, emit_migration_shim, strip_c_function,
)


def test_scalar_abi_export():
    w = emit_c_abi_export("crc32", "scalar", "u32")
    assert 'pub extern "C" fn crc32(data: *const u8, len: usize) -> u32' in w
    assert "from_raw_parts(data, len)" in w      # raw ABI -> safe slice
    assert "crc32_safe(__s)" in w                # calls the verified safe core


def test_buffer_abi_export_copies_out():
    w = emit_c_abi_export("b64_encode", "buffer", "usize")
    assert "out: *mut u8" in w
    assert "copy_nonoverlapping" in w            # Vec result -> C out-buffer
    assert "__r.len()" in w                      # returns written length


def test_migration_shim_bundles_safe_core_and_export():
    shim = emit_migration_shim("sum", "scalar", "u32",
                               "pub fn sum_safe(s: &[u8]) -> u32 { s.iter().map(|&b| b as u32).sum() }")
    assert "pub fn sum_safe" in shim             # verified safe core present
    assert 'extern "C" fn sum' in shim           # + its C-ABI export
    # raw pointers appear ONLY in the wrapper, once
    assert shim.count("from_raw_parts") == 1


def test_strip_c_function_removes_only_the_target_definition():
    src = ("int helper(int x) { return x + 1; }\n"
           "unsigned checksum(const unsigned char *d, unsigned long n) { return 42; }\n"
           "int other(void) { return 1; }\n")
    out = strip_c_function(src, "checksum")
    assert "return 42" not in out           # target definition body gone
    assert "helper" in out and "other" in out   # siblings untouched
    assert out.count("checksum") == 0       # the whole def removed


def test_strip_c_function_keeps_prototype():
    src = "unsigned checksum(const unsigned char *d, unsigned long n);\nint main(void){ return 0; }\n"
    out = strip_c_function(src, "checksum")
    assert "checksum(const unsigned char *d, unsigned long n);" in out   # prototype is not a def
