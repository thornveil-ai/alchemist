"""Workspace assembler: unify per-module crates into one type-shared cargo workspace.

The pure assembly logic (item scanning, hoist identical shared items, leave name-conflicting
ones module-local, workspace TOML) is exercised with no toolchain. The `cargo build/test
--workspace` proof runs only when a cargo toolchain is present (skipped in stock CI)."""
import shutil

import pytest

from alchemist.workspace_assembler import (
    assemble_workspace,
    collect_module_crates,
    extract_top_items,
    verify_workspace,
)

SHARED_TABLE = "pub const TAB: [u32; 4] = [\n    0x1, 0x2,\n    0x3, 0x4,\n];"
HAVE_CARGO = shutil.which("cargo") is not None


def _make_module(work, mod, lib_rs):
    crate = work / mod / ".alchemist" / "output" / f"{mod}-rs"
    (crate / "src").mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        f'[workspace]\n[package]\nname = "{mod}-rs"\nversion = "0.1.0"\n'
        f'edition = "2021"\n\n[dependencies]\n', encoding="utf-8")
    (crate / "src" / "lib.rs").write_text(lib_rs, encoding="utf-8")


def test_item_scanner_handles_multiline_arrays_and_fns():
    items = extract_top_items(SHARED_TABLE + "\npub fn f() {}\npub struct S { a: u32 }")
    assert {i.name for i in items} == {"TAB", "S"}  # fn is not a hoistable item
    tab = next(i for i in items if i.name == "TAB")
    assert tab.kind == "const" and tab.text.strip().endswith("];")


def _fixture(work):
    _make_module(work, "crc_a", SHARED_TABLE + "\npub fn crc_a() -> u32 { TAB[0] }\n")
    _make_module(work, "crc_b", SHARED_TABLE + "\npub fn crc_b() -> u32 { TAB[1] }\n")
    _make_module(work, "crc_c", "pub const POLY: u32 = 0xEDB88320;\npub fn crc_c() -> u32 { POLY }\n")
    _make_module(work, "crc_d", "pub const POLY: u32 = 0x04C11DB7;\npub fn crc_d() -> u32 { POLY }\n")


def test_hoist_identical_and_keep_conflicts_local(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _fixture(work)
    crates = collect_module_crates(work)
    assert set(crates) == {"crc_a", "crc_b", "crc_c", "crc_d"}

    out = tmp_path / "ws"
    plan = assemble_workspace(crates, out, "libcrc")

    # Identical table shared by two modules → hoisted to the shared types crate.
    assert plan.hoisted == ["TAB"]
    assert plan.types_crate == "libcrc-types"
    assert "pub const TAB" in (out / "libcrc-types" / "src" / "lib.rs").read_text(encoding="utf-8")
    a = (out / "crc_a-rs" / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "pub const TAB" not in a and "use libcrc_types::*;" in a

    # Same name, different body → NEVER merged; left in each module.
    assert plan.conflicts == ["POLY"]
    assert "0xEDB88320" in (out / "crc_c-rs" / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "0x04C11DB7" in (out / "crc_d-rs" / "src" / "lib.rs").read_text(encoding="utf-8")

    # Workspace manifest lists the types crate first, then members; nested [workspace] stripped.
    ws = (out / "Cargo.toml").read_text(encoding="utf-8")
    assert "[workspace]" in ws and '"libcrc-types"' in ws and '"crc_a-rs"' in ws
    assert "[workspace]" not in (out / "crc_a-rs" / "Cargo.toml").read_text(encoding="utf-8")


def _make_multicrate_module(work, mod):
    """A module whose output is a mini-workspace: an `-algo` crate path-depending on a
    `-core` crate (the real libcrc crc64 shape). Both must be carried into the workspace."""
    output = work / mod / ".alchemist" / "output"
    core = output / f"{mod}-core"
    algo = output / f"{mod}-algo"
    (core / "src").mkdir(parents=True)
    (core / "Cargo.toml").write_text(
        f'[package]\nname = "{mod}-core"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n',
        encoding="utf-8")
    (core / "src" / "lib.rs").write_text("pub fn seed() -> u32 { 7 }\n", encoding="utf-8")
    (algo / "src").mkdir(parents=True)
    (algo / "Cargo.toml").write_text(
        f'[package]\nname = "{mod}-algo"\nversion = "0.1.0"\nedition = "2021"\n\n'
        f'[dependencies]\n{mod}-core = {{ path = "../{mod}-core" }}\n', encoding="utf-8")
    (algo / "src" / "lib.rs").write_text(
        f"pub fn go() -> u32 {{ {mod.replace('-', '_')}_core::seed() + 1 }}\n"
        "#[cfg(test)]\nmod t { use super::*; #[test] fn ok() { assert_eq!(go(), 8); } }\n",
        encoding="utf-8")
    # a stray cargo target dir that must NOT be copied
    (output / "target").mkdir(parents=True, exist_ok=True)
    (output / "target" / "junk").write_text("x", encoding="utf-8")


def test_multicrate_module_carries_all_crates(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _make_multicrate_module(work, "crc64")
    crates = collect_module_crates(work)
    assert set(crates) == {"crc64"}
    out = tmp_path / "ws"
    plan = assemble_workspace(crates, out, "libcrc")
    # BOTH crates land; the intra-module path dep is preserved; target/ excluded.
    assert set(plan.members) == {"crc64-algo", "crc64-core"}
    assert (out / "crc64-core" / "Cargo.toml").is_file()
    assert '../crc64-core' in (out / "crc64-algo" / "Cargo.toml").read_text(encoding="utf-8")
    assert not (out / "target").exists()


@pytest.mark.skipif(not HAVE_CARGO, reason="cargo toolchain not present")
def test_assembled_workspace_builds_and_tests(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _fixture(work)
    _make_multicrate_module(work, "crc64")  # include a multi-crate module in the build
    out = tmp_path / "ws"
    assemble_workspace(collect_module_crates(work), out, "libcrc")
    receipt = verify_workspace(out)
    assert receipt.build_ok, receipt.build_log[-2000:]
    assert receipt.test_ok, receipt.test_log[-2000:]
