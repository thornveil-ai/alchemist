"""Assemble per-module translated crates into ONE verified cargo workspace.

Per-module orchestration (`lib_orchestrator`) translates each library `.c` into its own
independent single crate — good for clearing the architect's whole-library wall, but a real
library is ONE workspace with a shared type model, not N unrelated crates. This module closes
that gap (the Phase 2 exit deliverable):

  1. collect each module's verified output crate,
  2. run a **type-unification pass** — top-level items (const tables, statics, shared
     structs/enums) that are DEFINED IDENTICALLY in two or more modules are hoisted into a
     single shared `<lib>-types` crate that the members depend on; genuinely CONFLICTING
     definitions (same name, different body — e.g. crc64's per-variant `crc_tab64`) are left
     module-local and reported, never silently merged,
  3. write the `[workspace]` Cargo.toml,
  4. verify the whole tree compiles + tests TOGETHER (`cargo build/test --workspace`) — the
     one-type-universe proof.

No model calls happen here: this operates on already-generated, already-verified Rust on
disk, so it is fully testable offline (with a local cargo toolchain).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_OPEN = {"(": ")", "[": "]", "{": "}"}
_CLOSE = {")", "]", "}"}
_ITEM_RE = re.compile(r"\bpub\s+(const|static|struct|enum|type)\s+([A-Za-z_]\w*)")


def _crate_ident(name: str) -> str:
    """Cargo crate name (`foo-bar`) → extern-crate identifier (`foo_bar`)."""
    return name.replace("-", "_")


def _item_end(src: str, start: int) -> int:
    """Return the index one past the end of a top-level item beginning at `start`.

    A `const`/`static`/`type` ends at the first `;` at bracket-depth 0. A `struct`/`enum`
    with a body ends at the `}` that returns to depth 0; a unit/tuple `struct` (no brace)
    ends at its `;`. Tracks (), [] and {} so array literals and generics don't fool it.
    """
    depth = 0
    opened_brace = False
    i = start
    n = len(src)
    while i < n:
        c = src[i]
        if c in _OPEN:
            if c == "{":
                opened_brace = True
            depth += 1
        elif c in _CLOSE:
            depth -= 1
            if depth == 0 and opened_brace:
                return i + 1
        elif c == ";" and depth == 0:
            return i + 1
        i += 1
    return n


@dataclass
class TopItem:
    kind: str
    name: str
    text: str


def extract_top_items(src: str) -> list[TopItem]:
    """Extract top-level `pub` const/static/struct/enum/type items from Rust source."""
    items: list[TopItem] = []
    pos = 0
    while True:
        m = _ITEM_RE.search(src, pos)
        if not m:
            break
        start = m.start()
        end = _item_end(src, start)
        items.append(TopItem(m.group(1), m.group(2), src[start:end]))
        pos = end
    return items


def _norm(text: str) -> str:
    """Whitespace-normalized item body for identity comparison."""
    return re.sub(r"\s+", " ", text).strip()


def _crate_src_files(crate: Path) -> list[Path]:
    src = crate / "src"
    return sorted(src.rglob("*.rs")) if src.is_dir() else []


@dataclass
class WorkspacePlan:
    root: Path
    members: list[str]
    types_crate: str | None
    hoisted: list[str] = field(default_factory=list)      # names moved to the types crate
    conflicts: list[str] = field(default_factory=list)    # same name, different body — left local


def _member_crates(output: Path) -> list[Path]:
    """Every crate dir inside a module's output workspace (a module output is itself a
    mini-workspace, e.g. `crc64-algo` + `crc64-core`). Excludes the cargo `target/` dir."""
    return [p for p in sorted(output.iterdir())
            if p.is_dir() and p.name != "target"
            and (p / "Cargo.toml").is_file() and (p / "src").is_dir()]


def collect_module_crates(work_root: Path) -> dict[str, Path]:
    """Map module name → its generated output WORKSPACE dir, from a lib_orchestrator work
    tree (`<work>/<mod>/.alchemist/output/`). A module output is a mini-workspace that may
    hold several crates (an `-algo` crate path-depending on a `-core` crate); the assembler
    carries them ALL, so those intra-module deps keep resolving."""
    work_root = Path(work_root)
    out: dict[str, Path] = {}
    for mod_dir in sorted(p for p in work_root.iterdir() if p.is_dir()):
        output = mod_dir / ".alchemist" / "output"
        if output.is_dir() and _member_crates(output):
            out[mod_dir.name] = output
    return out


def assemble_workspace(module_outputs: dict[str, Path], out_dir: Path,
                       lib_name: str) -> WorkspacePlan:
    """Copy every crate of each module output into `out_dir`, hoist identical shared items
    into `<lib>-types`, and write the `[workspace]` Cargo.toml. Returns the plan (members,
    hoisted, conflicts). Each value in `module_outputs` is a module's output workspace dir,
    which may contain several crates; all are carried so intra-module path deps still resolve."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Copy every member crate of every module in, learning each crate's package name.
    members: list[str] = []
    crate_dirs: dict[str, Path] = {}
    for mod, output in module_outputs.items():
        for crate in _member_crates(output):
            pkg = _package_name(crate) or crate.name
            if pkg in crate_dirs:
                # Distinct crate name per module is expected (names are module-prefixed);
                # a genuine clash would break sibling path deps, so refuse rather than
                # silently overwrite.
                raise ValueError(
                    f"crate name collision '{pkg}' between modules — cannot assemble safely")
            dest = out_dir / pkg
            shutil.copytree(crate, dest)
            shutil.rmtree(dest / "target", ignore_errors=True)
            _strip_nested_workspace(dest)
            members.append(pkg)
            crate_dirs[pkg] = dest

    # Find every top-level item per member, grouped by name.
    #   name -> {pkg -> (normalized_body, TopItem, src_file)}
    by_name: dict[str, dict[str, tuple[str, TopItem, Path]]] = {}
    for pkg, dest in crate_dirs.items():
        for rs in _crate_src_files(dest):
            text = rs.read_text(encoding="utf-8", errors="replace")
            for it in extract_top_items(text):
                by_name.setdefault(it.name, {}).setdefault(
                    pkg, (_norm(it.text), it, rs))

    types_pkg = f"{lib_name}-types"
    hoisted: list[TopItem] = []
    conflicts: list[str] = []
    members_importing: set[str] = set()

    for name, per_pkg in by_name.items():
        if len(per_pkg) < 2:
            continue  # not shared across modules — leave it where it is
        bodies = {norm for (norm, _it, _f) in per_pkg.values()}
        if len(bodies) > 1:
            conflicts.append(name)         # same name, different definition — never merge
            continue
        # Identical in every module that defines it → hoist one copy, strip the rest.
        _norm_body, item, _f = next(iter(per_pkg.values()))
        hoisted.append(item)
        for pkg, (_n, it, rs) in per_pkg.items():
            _remove_item(rs, it)
            members_importing.add(pkg)

    types_crate: str | None = None
    if hoisted:
        types_crate = types_pkg
        _write_types_crate(out_dir / types_pkg, types_pkg, hoisted)
        for pkg in members_importing:
            _add_types_dep(crate_dirs[pkg], types_pkg)
            _add_glob_import(crate_dirs[pkg], types_pkg)
        members = [types_pkg] + members  # types crate first, like zlib-types

    _write_workspace_toml(out_dir, members)
    return WorkspacePlan(
        root=out_dir, members=members, types_crate=types_crate,
        hoisted=[i.name for i in hoisted], conflicts=conflicts)


# ---- crate file surgery -------------------------------------------------------------

def _package_name(crate: Path) -> str | None:
    m = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', (crate / "Cargo.toml").read_text(
        encoding="utf-8", errors="replace"))
    return m.group(1) if m else None


def _strip_nested_workspace(crate: Path) -> None:
    """A per-module output crate may carry its own single-member `[workspace]`; a member of
    an outer workspace must not declare one. Remove any nested `[workspace]` table."""
    toml = crate / "Cargo.toml"
    text = toml.read_text(encoding="utf-8", errors="replace")
    if "[workspace]" not in text:
        return
    lines = text.splitlines(keepends=True)
    out, skip = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith("[") and s != "[workspace]":
            skip = False
        if s == "[workspace]":
            skip = True
            continue
        if not skip:
            out.append(ln)
    toml.write_text("".join(out), encoding="utf-8")


def _remove_item(rs: Path, item: TopItem) -> None:
    text = rs.read_text(encoding="utf-8", errors="replace")
    idx = text.find(item.text)
    if idx == -1:
        return
    text = text[:idx] + text[idx + len(item.text):]
    rs.write_text(text, encoding="utf-8")


def _add_types_dep(crate: Path, types_pkg: str) -> None:
    toml = crate / "Cargo.toml"
    text = toml.read_text(encoding="utf-8", errors="replace")
    dep = f'{types_pkg} = {{ path = "../{types_pkg}" }}'
    if dep in text:
        return
    if "[dependencies]" in text:
        text = text.replace("[dependencies]", f"[dependencies]\n{dep}", 1)
    else:
        text = text.rstrip() + f"\n\n[dependencies]\n{dep}\n"
    toml.write_text(text, encoding="utf-8")


def _add_glob_import(crate: Path, types_pkg: str) -> None:
    """Add `use <ident>::*;` to the crate root so hoisted items resolve by bare name."""
    lib_rs = crate / "src" / "lib.rs"
    if not lib_rs.is_file():
        srcs = _crate_src_files(crate)
        if not srcs:
            return
        lib_rs = srcs[0]
    text = lib_rs.read_text(encoding="utf-8", errors="replace")
    use = f"use {_crate_ident(types_pkg)}::*;"
    if use in text:
        return
    # Inner attributes (`#![forbid(unsafe_code)]`, `#![allow(...)]`) and inner doc comments
    # (`//!`) MUST stay at the crate root's top — inserting a `use` before them is a compile
    # error ("inner attribute not permitted"). Skip past that leading block, then insert.
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        s = lines[i].lstrip()
        if s.startswith("#![") or s.startswith("//!") or s.strip() == "":
            i += 1
        else:
            break
    lines.insert(i, use + "\n")
    lib_rs.write_text("".join(lines), encoding="utf-8")


def _write_types_crate(dest: Path, pkg: str, items: list[TopItem]) -> None:
    (dest / "src").mkdir(parents=True, exist_ok=True)
    (dest / "Cargo.toml").write_text(
        f'[package]\nname = "{pkg}"\nversion = "0.1.0"\nedition = "2021"\n\n'
        f"[dependencies]\n", encoding="utf-8")
    body = "//! Shared type model hoisted from modules with identical definitions.\n\n"
    body += "\n\n".join(it.text.strip() for it in items) + "\n"
    (dest / "src" / "lib.rs").write_text(body, encoding="utf-8")


def _write_workspace_toml(out_dir: Path, members: list[str]) -> None:
    body = '[workspace]\nresolver = "2"\nmembers = [\n'
    body += "".join(f'    "{m}",\n' for m in members)
    body += "]\n"
    (out_dir / "Cargo.toml").write_text(body, encoding="utf-8")


# ---- verification -------------------------------------------------------------------

@dataclass
class WorkspaceReceipt:
    build_ok: bool
    test_ok: bool
    build_log: str = ""
    test_log: str = ""


def verify_workspace(out_dir: Path, *, run_tests: bool = True,
                     timeout: int = 1800) -> WorkspaceReceipt:
    """`cargo build --workspace` then (optionally) `cargo test --workspace`. The whole tree
    compiling + testing as one unit IS the type-unification proof."""
    out_dir = Path(out_dir)

    def _run(args: list[str]) -> tuple[bool, str]:
        try:
            r = subprocess.run(["cargo", *args], cwd=out_dir, capture_output=True,
                               text=True, timeout=timeout)
            return r.returncode == 0, (r.stdout or "") + "\n" + (r.stderr or "")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return False, f"{type(e).__name__}: {e}"

    build_ok, build_log = _run(["build", "--workspace"])
    test_ok, test_log = (True, "skipped")
    if build_ok and run_tests:
        test_ok, test_log = _run(["test", "--workspace"])
    return WorkspaceReceipt(build_ok, test_ok, build_log, test_log)
