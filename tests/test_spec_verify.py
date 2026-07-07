"""Algorithmic verification — KAT / property / divergence (correctness, not just ==C).

The end-to-end (KAT catches a spec deviation; roundtrip holds over 256 lengths;
divergence fingers an overflow-buggy C) is proven on the box; here we lock the test
generators and the divergence logic.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from alchemist.autonomy.spec_verify import (
    kat_test_source, roundtrip_property, divergence_verdict,
)


def test_kat_test_source_emits_assertions():
    src = kat_test_source("hash(input)", [("&[1u8, 2]", "&[3u8]"), ("&[0u8]", "&[0u8]")])
    assert "assert_eq!(hash(input).as_slice()" in src
    assert "&[1u8, 2]" in src and "&[3u8]" in src        # standard vectors, not C outputs


def test_roundtrip_property_emits_invariant():
    src = roundtrip_property("enc", "dec", n=64)
    assert "dec(&enc(&v))" in src                        # decode(encode(x)) == x
    assert "0..64" in src and "roundtrip broken" in src  # over many generated inputs


def _sanitizers_work():
    if not shutil.which("gcc"):
        return False
    d = Path(tempfile.mkdtemp())
    (d / "t.c").write_text("int main(){return 0;}")
    if subprocess.run(["gcc", "-fsanitize=undefined", str(d / "t.c"), "-o", str(d / "t")],
                      capture_output=True).returncode:
        return False
    return subprocess.run([str(d / "t")], capture_output=True).returncode == 0


@pytest.mark.skipif(not _sanitizers_work(), reason="needs a working UBSan toolchain")
def test_divergence_inconclusive_on_well_defined_c(tmp_path):
    # a well-defined (unsigned, wrapping) C exhibits no UB -> inconclusive, not c-buggy
    clean = ("unsigned accum(const unsigned char *d, unsigned long n){ unsigned a=0; "
             "for(unsigned long i=0;i<n;i++) a=a*257u+d[i]; return a; }")
    driver = ("#include <stdio.h>\nint main(){ unsigned char b[64]; "
              "unsigned long n=fread(b,1,64,stdin); volatile long r=accum(b,n); (void)r; return 0; }")
    verdict = divergence_verdict(clean, driver, [bytes([255]) * i for i in range(1, 12)], tmp_path)
    assert verdict == "inconclusive"
