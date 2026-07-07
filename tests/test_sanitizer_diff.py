"""Item 3 — sanitizer-diff: surface latent UB in the C the safe Rust eliminates."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from alchemist.verifier.sanitizer_diff import _UB, sanitizer_check


def _sanitizers_work() -> bool:
    """gcc present AND a trivial ASan+UBSan binary both compiles and runs (MinGW on
    Windows has gcc but no working sanitizer runtime -> skip there)."""
    if not shutil.which("gcc"):
        return False
    d = Path(tempfile.mkdtemp())
    (d / "t.c").write_text("int main(){return 0;}")
    if subprocess.run(["gcc", "-fsanitize=address,undefined", str(d / "t.c"), "-o", str(d / "t")],
                      capture_output=True).returncode:
        return False
    return subprocess.run([str(d / "t")], capture_output=True).returncode == 0


_SAN = _sanitizers_work()


def test_ub_regex_extracts_ubsan_finding():
    line = ("san.c:2:40: runtime error: signed integer overflow: 100 * 257 "
            "cannot be represented in type 'int'")
    m = _UB.search(line)
    assert m and "signed integer overflow" in (m.group(1) or "")


def test_ub_regex_extracts_asan_finding():
    m = _UB.search("ERROR: AddressSanitizer: heap-buffer-overflow on address 0x...")
    assert m and (m.group(2) or "").startswith("heap-buffer-overflow")


@pytest.mark.skipif(not _SAN, reason="needs a working ASan/UBSan toolchain")
def test_sanitizer_catches_signed_overflow(tmp_path):
    buggy = ("int f(const unsigned char *d, unsigned long n) {\n"
             "    int a = 0;\n    for (unsigned long i = 0; i < n; i++) a = a * 257 + d[i];\n"
             "    return a;\n}\n")
    driver = ("#include <stdio.h>\nint main(){ unsigned char b[64]; "
              "unsigned long n=fread(b,1,64,stdin); volatile long r=f(b,n); (void)r; return 0; }")
    findings = sanitizer_check(buggy, driver, [bytes([255]) * i for i in range(1, 12)], tmp_path)
    assert any("overflow" in x for x in findings)


@pytest.mark.skipif(not _SAN, reason="needs a working ASan/UBSan toolchain")
def test_sanitizer_clean_on_wrapping_unsigned(tmp_path):
    clean = ("unsigned f(const unsigned char *d, unsigned long n) {\n"
             "    unsigned a = 0;\n    for (unsigned long i = 0; i < n; i++) a = a * 257u + d[i];\n"
             "    return a;\n}\n")
    driver = ("#include <stdio.h>\nint main(){ unsigned char b[64]; "
              "unsigned long n=fread(b,1,64,stdin); volatile long r=f(b,n); (void)r; return 0; }")
    assert sanitizer_check(clean, driver, [bytes([255]) * i for i in range(1, 12)], tmp_path) == []


def test_divergence_verdict_c_buggy_on_signed_overflow(tmp_path):
    # divergence analysis: when Rust != C and the C has UB, verdict is c-buggy
    from alchemist.verifier.sanitizer_diff import divergence_verdict
    if not _SAN:
        import pytest; pytest.skip("needs ASan/UBSan toolchain")
    buggy = ("int f(const unsigned char *d, unsigned long n){ int a=0; "
             "for(unsigned long i=0;i<n;i++) a=a*257+d[i]; return a; }")
    driver = ("#include <stdio.h>\nint main(){ unsigned char b[64]; "
              "unsigned long n=fread(b,1,64,stdin); volatile long r=f(b,n); (void)r; return 0; }")
    assert divergence_verdict(buggy, driver, [bytes([255])*i for i in range(1,12)], tmp_path) == "c-buggy"
