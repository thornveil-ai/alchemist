"""Tests for alchemist.implementer.test_generator (Phase 4B)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from alchemist.architect.schemas import CrateArchitecture, CrateSpec
from alchemist.extractor.schemas import (
    AlgorithmSpec,
    ModuleSpec,
    Parameter,
    TestVector,
)
from alchemist.implementer.skeleton import generate_workspace_skeleton
from alchemist.implementer.test_generator import (
    _build_call,
    emit_module_test_block,
    generate_tests_for_workspace,
)


def _cargo_available() -> bool:
    try:
        subprocess.run(["cargo", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# ---------- Emission ----------

def test_emit_test_block_uses_catalog_for_adler32():
    alg = AlgorithmSpec(
        name="adler32",
        display_name="Adler-32",
        category="checksum",
        description="RFC 1950 Adler-32.",
        inputs=[Parameter(name="input", rust_type="&[u8]", description="input bytes")],
        return_type="u32",
    )
    module = ModuleSpec(
        name="checksum",
        display_name="Checksums",
        description="",
        algorithms=[alg],
    )
    src, stats = emit_module_test_block(module)
    assert stats["catalog"] >= 1
    # Canonical RFC 1950 Wikipedia test
    assert "11e60398" in src
    # Tests call through `super::adler32`
    assert "super::adler32" in src


def test_emit_test_block_uses_spec_test_vectors():
    alg = AlgorithmSpec(
        name="custom_add",
        display_name="Custom add",
        category="utility",
        description="",
        inputs=[
            Parameter(name="a", rust_type="u32", description="first"),
            Parameter(name="b", rust_type="u32", description="second"),
        ],
        return_type="u32",
        test_vectors=[
            TestVector(
                description="1 + 2 == 3",
                inputs={"a": "1", "b": "2"},
                expected_output="3",
                tolerance="exact",
            ),
        ],
    )
    module = ModuleSpec(name="math", display_name="Math", description="", algorithms=[alg])
    src, stats = emit_module_test_block(module)
    assert stats["spec"] == 1
    assert "test_custom_add_spec_0" in src
    assert "super::custom_add(a, b)" in src


def _option_alg(expected: str) -> ModuleSpec:
    alg = AlgorithmSpec(
        name="compress_bound_z",
        display_name="compressBound_z",
        category="utility",
        description="",
        inputs=[Parameter(name="source_len", rust_type="usize", description="")],
        return_type="Option<usize>",
        test_vectors=[
            TestVector(
                description="fuzz_input_len_0",
                inputs={"source_len": "0usize"},
                expected_output=expected,
                tolerance="exact",
            ),
        ],
    )
    return ModuleSpec(name="compress", display_name="", description="", algorithms=[alg])


def test_option_some_expected_renders_as_constructor_not_byte_string():
    """Regression: Some(18usize) vs Option<usize> return must render verbatim,
    not as b\"Some(18usize)\" (which poisoned the whole module's compile)."""
    src, stats = emit_module_test_block(_option_alg("Some(18usize)"))
    assert stats["spec"] == 1
    assert "assert_eq!(got, Some(18usize)," in src
    assert 'b"Some(' not in src


def test_option_none_expected_renders_verbatim():
    src, _ = emit_module_test_block(_option_alg("None"))
    assert "assert_eq!(got, None," in src
    assert 'b"None"' not in src


def test_unrenderable_expected_emits_failing_test_not_mangled_literal():
    """A value the renderer can't express for the return type must produce a
    test that FAILS with an explanation — never a mangled byte-string that
    breaks compilation and vacuously skips the gate."""
    alg = AlgorithmSpec(
        name="mystery",
        display_name="",
        category="utility",
        description="",
        inputs=[Parameter(name="x", rust_type="u32", description="")],
        return_type="u32",
        test_vectors=[
            TestVector(
                description="bad",
                inputs={"x": "1u32"},
                expected_output="SomeOpaqueStruct { a: 1 }",
                tolerance="exact",
            ),
        ],
    )
    module = ModuleSpec(name="m", display_name="", description="", algorithms=[alg])
    src, _ = emit_module_test_block(module)
    assert "UNRENDERABLE" in src
    assert "panic!" in src
    assert 'b"SomeOpaqueStruct' not in src
    # Braces must be escaped for the panic! FORMAT string, or the failing
    # test itself becomes a compile error and poisons the module.
    assert "{{ a: 1 }}" in src
    assert "` for return" in src  # message still readable


def test_bytes_like_return_keeps_byte_string_fallback():
    alg = AlgorithmSpec(
        name="render_bytes",
        display_name="",
        category="utility",
        description="",
        inputs=[Parameter(name="x", rust_type="u32", description="")],
        return_type="Vec<u8>",
        test_vectors=[
            TestVector(
                description="bytes out",
                inputs={"x": "1u32"},
                expected_output="abc",
                tolerance="exact",
            ),
        ],
    )
    module = ModuleSpec(name="m", display_name="", description="", algorithms=[alg])
    src, _ = emit_module_test_block(module)
    assert 'assert_eq!(got, b"abc",' in src


def test_build_call_single_slice_fn():
    """Adler-32-style one-slice signature gets a one-arg call."""
    alg = AlgorithmSpec(
        name="adler32", display_name="", category="checksum",
        description="",
        inputs=[Parameter(name="input", rust_type="&[u8]", description="")],
        return_type="u32",
    )
    assert _build_call("adler32", alg) == "super::adler32(input)"


def test_build_call_three_arg_signature_canonical_seed():
    """C-style `adler32(seed, buf, len)` gets `(1u32, input, input.len())`."""
    alg = AlgorithmSpec(
        name="adler32", display_name="", category="checksum",
        description="",
        inputs=[
            Parameter(name="seed", rust_type="u32", description=""),
            Parameter(name="buf",  rust_type="&[u8]", description=""),
            Parameter(name="len",  rust_type="usize", description=""),
        ],
        return_type="u32",
    )
    call = _build_call("adler32", alg)
    assert call == "super::adler32(1u32, input, input.len())"


def test_build_call_crc32_seed_defaults_to_zero():
    alg = AlgorithmSpec(
        name="crc32", display_name="", category="checksum",
        description="",
        inputs=[
            Parameter(name="seed", rust_type="u32", description=""),
            Parameter(name="buf",  rust_type="&[u8]", description=""),
            Parameter(name="len",  rust_type="usize", description=""),
        ],
        return_type="u32",
    )
    call = _build_call("crc32", alg)
    assert call == "super::crc32(0u32, input, input.len())"


def test_build_call_with_no_inputs_falls_back():
    assert _build_call("foo", None) == "super::foo(input)"


def test_generated_catalog_test_uses_full_signature_for_adler32():
    alg = AlgorithmSpec(
        name="adler32", display_name="", category="checksum",
        description="",
        inputs=[
            Parameter(name="seed", rust_type="u32", description=""),
            Parameter(name="buf",  rust_type="&[u8]", description=""),
            Parameter(name="len",  rust_type="usize", description=""),
        ],
        return_type="u32",
    )
    module = ModuleSpec(
        name="checksum", display_name="", description="",
        algorithms=[alg],
    )
    src, _stats = emit_module_test_block(module)
    # The Wikipedia catalog test must call with full signature
    assert "super::adler32(1u32, input, input.len())" in src


def test_emit_test_block_smoke_when_empty_and_enabled():
    alg = AlgorithmSpec(
        name="mystery",
        display_name="Mystery",
        category="utility",
        description="",
        inputs=[Parameter(name="input", rust_type="&[u8]", description="")],
        return_type="()",
    )
    module = ModuleSpec(name="misc", display_name="Misc", description="", algorithms=[alg])
    src, stats = emit_module_test_block(module, enable_smoke=True)
    assert stats["smoke"] == 1
    assert "smoke_mystery" in src


# ---------- Integration with skeleton ----------

@pytest.mark.skipif(not _cargo_available(), reason="cargo not on PATH")
def test_tests_fail_on_skeleton_by_design(tmp_path):
    """The end-to-end Phase A+B smoke test.

    1. Generate skeleton (unimplemented!() bodies).
    2. Append spec + catalog tests to each module file.
    3. Run cargo test.
    4. Expect: compiles OK (still meets TDD skeleton bar), tests FAIL
       because the stubs panic with unimplemented!().
    """
    alg = AlgorithmSpec(
        name="adler32",
        display_name="Adler-32",
        category="checksum",
        description="RFC 1950 Adler-32.",
        inputs=[Parameter(name="input", rust_type="&[u8]", description="bytes")],
        return_type="u32",
    )
    module = ModuleSpec(
        name="checksum",
        display_name="Checksums",
        description="",
        algorithms=[alg],
    )
    arch = CrateArchitecture(
        workspace_name="zlib_rs",
        description="",
        crates=[
            CrateSpec(
                name="zlib-checksum",
                description="",
                modules=["checksum"],
                is_no_std=False,  # std needed for format!/String in tests
            ),
        ],
    )
    skel = generate_workspace_skeleton([module], arch, tmp_path, cargo_check=True)
    assert skel.ok, f"skeleton must compile: {skel.workspace_stderr[:1500]}"

    results = generate_tests_for_workspace([module], arch, tmp_path)
    assert len(results) == 1
    assert results[0].tests_written >= 1

    # Re-run cargo check (tests still need to compile)
    check = subprocess.run(
        ["cargo", "check", "--all-targets"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert check.returncode == 0, (
        f"cargo check --all-targets failed after test gen:\n"
        f"{check.stderr[:3000]}"
    )

    # Tests should FAIL (panic on unimplemented!()) — this is the TDD design
    test_run = subprocess.run(
        ["cargo", "test", "--no-fail-fast"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert test_run.returncode != 0, (
        "tests against skeleton stubs must FAIL (TDD forcing function)"
    )
    combined = test_run.stdout + "\n" + test_run.stderr
    assert "unimplemented" in combined.lower() or "panic" in combined.lower(), (
        f"expected panic-on-unimplemented, got:\n{combined[:2000]}"
    )


# ---------- static-table initializer no-op + const-scope prompt (M09) ----------

def test_noop_table_init_recognizes_lazy_static_initializers():
    from alchemist.implementer.init_templates import (
        is_noop_table_init, noop_table_init_template,
    )
    from alchemist.extractor.schemas import AlgorithmSpec
    for name in ("crc32_init_table", "make_crc_table", "init_hash_table"):
        alg = AlgorithmSpec(name=name, display_name=name, category="checksum",
                            description="", inputs=[], return_type="()")
        assert is_noop_table_init(alg), name
        code = noop_table_init_template(alg)
        assert code.startswith(f"pub fn {name}()")
        assert "no-op" in code


def test_noop_table_init_rejects_functions_with_inputs_or_returns():
    from alchemist.implementer.init_templates import is_noop_table_init
    from alchemist.extractor.schemas import AlgorithmSpec, Parameter
    # crc32 itself (has inputs) must NOT be no-op'd
    with_inputs = AlgorithmSpec(
        name="crc32", display_name="", category="checksum", description="",
        inputs=[Parameter(name="buf", rust_type="&[u8]", description="")],
        return_type="u32")
    assert not is_noop_table_init(with_inputs)
    # A "table" fn that returns data is not a no-op initializer
    returns_data = AlgorithmSpec(
        name="get_crc_table", display_name="", category="checksum",
        description="", inputs=[], return_type="&'static [u32]")
    assert not is_noop_table_init(returns_data)


def test_consts_in_scope_lists_module_constants():
    from alchemist.implementer.tdd_generator import TDDGenerator
    src = ("pub const CRC32_TABLE: [u32; 256] = [0; 256];\n"
           "const NMAX: usize = 5552;\n"
           "static POLY: u32 = 0xEDB88320;\n"
           "pub fn crc32() {}\n")
    listed = TDDGenerator._consts_in_scope(src)
    assert "CRC32_TABLE" in listed and "NMAX" in listed and "POLY" in listed


def test_consts_in_scope_empty_when_none():
    from alchemist.implementer.tdd_generator import TDDGenerator
    listed = TDDGenerator._consts_in_scope("pub fn f() {}\n")
    assert "compute" in listed.lower()
