"""Tests for the reference probe module."""

from __future__ import annotations

from pathlib import Path

import pytest

from alchemist.extractor.schemas import AlgorithmSpec, Parameter
from alchemist.implementer.reference_probe import (
    ProbeResult,
    _find_body_in_sources,
    extract_c_function_body,
    probe_result_as_reference,
)


ZLIB_SRC = Path(__file__).parent.parent / "subjects" / "zlib"


def _zlib_available() -> bool:
    return (ZLIB_SRC / "adler32.c").exists()


@pytest.mark.skipif(not _zlib_available(), reason="zlib subject not present")
def test_extract_body_adler32_z():
    body = extract_c_function_body(ZLIB_SRC / "adler32.c", "adler32_z")
    assert body is not None
    assert "adler32_z" in body
    assert "BASE" in body  # references the zlib Adler modulus


@pytest.mark.skipif(not _zlib_available(), reason="zlib subject not present")
def test_extract_body_missing_returns_none():
    body = extract_c_function_body(ZLIB_SRC / "adler32.c", "not_a_real_function")
    assert body is None


def test_extract_body_nonexistent_file_returns_none():
    body = extract_c_function_body(Path("no/such/file.c"), "anything")
    assert body is None


@pytest.mark.skipif(not _zlib_available(), reason="zlib subject not present")
def test_find_body_in_sources_uses_source_files():
    alg = AlgorithmSpec(
        name="adler32_z",
        display_name="",
        category="checksum",
        description="",
        inputs=[Parameter(name="buf", rust_type="&[u8]", description="")],
        return_type="u32",
        source_functions=["adler32_z"],
        source_files=["adler32.c"],
    )
    body = _find_body_in_sources(alg, ZLIB_SRC)
    assert body is not None
    assert "adler32_z" in body


@pytest.mark.skipif(not _zlib_available(), reason="zlib subject not present")
def test_find_body_falls_back_to_rglob():
    alg = AlgorithmSpec(
        name="adler32_z",
        display_name="",
        category="checksum",
        description="",
        inputs=[Parameter(name="buf", rust_type="&[u8]", description="")],
        return_type="u32",
        source_functions=["adler32_z"],
        # source_files empty — probe must search
    )
    body = _find_body_in_sources(alg, ZLIB_SRC)
    assert body is not None


def test_probe_result_as_reference_on_success():
    probe = ProbeResult(
        algorithm="myfn",
        success=True,
        rust_source="pub fn myfn() {}",
    )
    ref = probe_result_as_reference(probe, "pub fn myfn()")
    assert ref is not None
    assert ref.algorithm == "myfn"
    assert ref.rust_source == "pub fn myfn() {}"
    assert ref.variant == "probe"


def test_probe_result_as_reference_on_failure():
    probe = ProbeResult(
        algorithm="myfn",
        success=False,
        error="compile failed",
    )
    ref = probe_result_as_reference(probe, "pub fn myfn()")
    assert ref is None


def test_probe_result_as_reference_empty_source():
    probe = ProbeResult(
        algorithm="myfn",
        success=True,
        rust_source="",  # success but empty — treat as failure
    )
    ref = probe_result_as_reference(probe, "pub fn myfn()")
    assert ref is None


def test_extract_referenced_macros_pulls_siprounds_transitively(tmp_path):
    """C libraries hide the load-bearing logic in function-like macros
    (SipHash's SIPROUND uses ROTL). The probe must pull every macro the
    body references, transitively, or the model guesses the rounds wrong."""
    from alchemist.implementer.reference_probe import extract_referenced_macros
    src = (
        "#define cROUNDS 2\n"
        "#define dROUNDS 4\n"
        "#define ROTL(x, b) ((x) << (b) | (x) >> (64 - (b)))\n"
        "#define UNUSED_MACRO(z) ((z) + 1)\n"
        "#define SIPROUND \\n"
        "    do { v0 += v1; v1 = ROTL(v1, 13); } while (0)\n"
    )
    body = "int f() { SIPROUND; for (i=0;i<dROUNDS;i++){} }"
    out = extract_referenced_macros(src, body)
    assert "#define SIPROUND" in out
    assert "ROTL" in out          # transitively via SIPROUND
    assert "dROUNDS" in out
    assert "UNUSED_MACRO" not in out  # not referenced → excluded


def test_extract_referenced_macros_empty_when_none_referenced():
    from alchemist.implementer.reference_probe import extract_referenced_macros
    src = "#define FOO 1\n#define BAR(x) (x)\n"
    assert extract_referenced_macros(src, "int f() { return 0; }") == ""


def test_c_string_array_carry_byte_exact():
    """String-table carry (codec codebooks) must be byte-exact: octal, hex, embedded NUL,
    \r\n, empty entries, and adjacent-literal concatenation."""
    from alchemist.implementer.reference_probe import (
        c_string_array_to_rust_const, _parse_c_string_array,
    )
    cdef = (
        'static char *T[6] = {"\002s,\266", "\xff\x00A", "\r\n", "",'
        ' "ab" "cd", "the"};'
    )
    name, rust = c_string_array_to_rust_const(cdef)
    assert name == "T"
    assert rust.startswith("pub const T: [&[u8]; 6] = [")
    body = cdef[cdef.index("{") + 1:cdef.rindex("}")]
    elems = _parse_c_string_array(body)
    assert elems == [
        bytes([2, ord("s"), ord(","), 0o266 & 0xFF]),  # octal \002 s , \266
        bytes([0xFF, 0x00, ord("A")]),                  # hex \xff, embedded NUL, A
        b"\r\n",                                          # \r \n
        b"",                                              # empty entry
        b"abcd",                                          # adjacent-literal concatenation
        b"the",
    ]
    # non-UTF-8 / control bytes render as \xNN in a byte-string literal
    assert 'b"\\x02s,\\xb6"' in rust and 'b"\\xff\\x00A"' in rust and 'b"\\x0d\\x0a"' in rust
