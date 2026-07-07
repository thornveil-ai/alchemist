"""Item 3 — sanitizer-diff: surface latent UB in the C the safe Rust eliminates."""

import shutil

import pytest

from alchemist.autonomy.sanitizer import _UB, sanitizer_check


def test_ub_regex_extracts_ubsan_finding():
    line = ("san.c:2:40: runtime error: signed integer overflow: 100 * 257 "
            "cannot be represented in type 'int'")
    m = _UB.search(line)
    assert m and "signed integer overflow" in (m.group(1) or "")


def test_ub_regex_extracts_asan_finding():
    m = _UB.search("ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...")
    assert m and (m.group(2) or "").startswith("heap-buffer-overflow")


@pytest.mark.skipif(not shutil.which("gcc"), reason="sanitizer-diff needs gcc")
def test_sanitizer_catches_signed_overflow(tmp_path):
    buggy = ("int f(const unsigned char *d, unsigned long n) {\n"
             "    int a = 0;\n    for (unsigned long i = 0; i < n; i++) a = a * 257 + d[i];\n"
             "    return a;\n}\n")
    driver = ("#include <stdio.h>\nint main(){ unsigned char b[64]; "
              "unsigned long n=fread(b,1,64,stdin); volatile long r=f(b,n); (void)r; return 0; }")
    findings = sanitizer_check(buggy, driver, [bytes([255]) * i for i in range(1, 12)], tmp_path)
    assert any("overflow" in x for x in findings)


@pytest.mark.skipif(not shutil.which("gcc"), reason="sanitizer-diff needs gcc")
def test_sanitizer_clean_on_wrapping_unsigned(tmp_path):
    clean = ("unsigned f(const unsigned char *d, unsigned long n) {\n"
             "    unsigned a = 0;\n    for (unsigned long i = 0; i < n; i++) a = a * 257u + d[i];\n"
             "    return a;\n}\n")
    driver = ("#include <stdio.h>\nint main(){ unsigned char b[64]; "
              "unsigned long n=fread(b,1,64,stdin); volatile long r=f(b,n); (void)r; return 0; }")
    assert sanitizer_check(clean, driver, [bytes([255]) * i for i in range(1, 12)], tmp_path) == []
