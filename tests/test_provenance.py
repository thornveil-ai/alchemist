"""Item B — safety audit, CWE-mapping, signed verification receipts."""

from alchemist.autonomy.provenance import (
    cwe_findings, safety_audit, SafetyReport, VerificationReceipt,
)


def test_cwe_findings_heap_and_indexing():
    cwes = dict(cwe_findings("char *p = malloc(n); free(p); p[i] = 0;"))
    assert "CWE-416" in cwes and "CWE-415" in cwes and "CWE-401" in cwes  # UAF/double-free/leak
    assert "CWE-125" in cwes                                              # OOB from raw indexing


def test_cwe_findings_string_funcs():
    cwes = dict(cwe_findings("strcpy(dst, src); sprintf(buf, fmt);"))
    assert "CWE-120" in cwes and "CWE-134" in cwes


def test_safety_audit_clean_rust_is_safe():
    r = safety_audit("pub fn f(s: &[u8]) -> u32 { s.iter().map(|&b| b as u32).sum() }")
    assert r.unsafe_blocks == 0 and r.raw_pointers == 0 and r.memory_safe


def test_safety_audit_unsafe_confined_to_ffi_is_safe():
    ffi = ('#[no_mangle] pub extern "C" fn f(p: *const u8, n: usize) -> u32 '
           '{ let s = unsafe { core::slice::from_raw_parts(p, n) }; s.len() as u32 }')
    r = safety_audit(ffi)
    assert r.unsafe_blocks == 1 and r.ffi_wrappers == 1 and r.memory_safe   # confined -> ok


def test_safety_audit_flags_stray_unsafe():
    r = safety_audit("pub fn f() { unsafe { *(0 as *const u8); } }")       # unsafe, no FFI
    assert not r.memory_safe


def test_receipt_digest_stable_and_attestable():
    r = VerificationReceipt("make_buffer", "verified", 40, 1.0,
                            SafetyReport(0, 0, 0, True), True, [("CWE-416", "uaf")], "gemma-4-31b")
    assert r.digest() == r.digest() and len(r.digest()) == 64   # stable content hash
    att = r.attest()
    assert att["sha256"] == r.digest() and "signature" in att   # signed field present
