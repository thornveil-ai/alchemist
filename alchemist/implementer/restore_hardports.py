"""Hydrate a generated workspace from the git-tracked hardport store.

The skeleton regen writes `unimplemented!()` stubs for every function. The
pipeline only restores verified bodies during the per-function fill loop —
so a regen followed by anything less than a full implement run leaves the
workspace full of stubs (and, worse, stubs whose signatures reference types
only *defined inside* a hardport, e.g. `make_crc_table -> CrcTables`, which
won't even compile).

This module makes the hardport store first-class: given a subject workspace,
it splices every matching hardport body (in
`references/impls/<subject>_hardports/<crate>/<module>/<fn>.rs`) over the
corresponding stub in `<workspace>/<crate>/src/<module>.rs`. Idempotent —
re-running replaces the same functions again. This is the durability
backbone: verified bodies live in git, and one call rehydrates a fresh
skeleton.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RestoreReport:
    restored: list[str]        # "crate::module::fn"
    missing_module: list[str]  # hardport with no matching workspace module
    no_stub: list[str]         # hardport whose fn wasn't found in the module

    def summary(self) -> str:
        return (f"{len(self.restored)} hardport(s) restored"
                + (f", {len(self.no_stub)} fn not found" if self.no_stub else "")
                + (f", {len(self.missing_module)} module(s) missing"
                   if self.missing_module else ""))


def _replace_fn(source: str, fn_name: str, replacement: str) -> str | None:
    """Replace the whole `pub fn <fn_name>(...) { ... }` (brace-matched) with
    `replacement`. Returns the new source, or None if the fn isn't found."""
    m = re.search(rf"(?:^|\n)([ \t]*)pub fn {re.escape(fn_name)}\b[^\n{{]*\{{",
                  source)
    if not m:
        return None
    start = m.start(1) if m.group(0).startswith("\n") else m.start()
    # find the opening brace of the fn body
    brace = source.index("{", m.start())
    depth = 0
    end = None
    for i in range(brace, len(source)):
        c = source[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    return source[:start].rstrip("\n") + "\n\n" + replacement.rstrip() + "\n" + source[end:]


def restore_hardports(
    subject_dir: Path, workspace_dir: Path, subject_hint: str | None = None,
) -> RestoreReport:
    """Splice every hardport for `subject_hint` over its stub in the workspace.

    subject_dir: e.g. subjects/zlib
    workspace_dir: e.g. subjects/zlib/.alchemist/output
    subject_hint: e.g. "zlib" (defaults to subject_dir.name)
    """
    from alchemist.references import registry as _reg
    hint = subject_hint or subject_dir.name
    hp_root = Path(_reg.REFERENCES_DIR) / f"{hint}_hardports"
    report = RestoreReport([], [], [])
    if not hp_root.exists():
        return report
    for hp in sorted(hp_root.rglob("*.rs")):
        rel = hp.relative_to(hp_root)
        if len(rel.parts) != 3:
            continue
        crate, module, fn_file = rel.parts
        fn_name = fn_file[:-3]  # strip .rs
        mod_path = workspace_dir / crate / "src" / f"{module}.rs"
        if not mod_path.exists():
            report.missing_module.append(f"{crate}::{module}")
            continue
        src = mod_path.read_text(encoding="utf-8")
        body = hp.read_text(encoding="utf-8")
        new_src = _replace_fn(src, fn_name, body)
        if new_src is None:
            report.no_stub.append(f"{crate}::{module}::{fn_name}")
            continue
        mod_path.write_text(new_src, encoding="utf-8")
        report.restored.append(f"{crate}::{module}::{fn_name}")
    return report
