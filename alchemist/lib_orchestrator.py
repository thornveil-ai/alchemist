"""Per-module orchestration for whole multi-module C libraries.

The architect stage can't design a large library (many interdependent modules) in one
shot. Instead, translate the library MODULE-BY-MODULE: each library `.c` becomes its own
single-module subject (with the library's shared headers, generated tables and `.inc`
files replicated so relative includes still resolve), translated by a separate
`alchemist translate` process. The per-module processes run CONCURRENTLY — the local vLLM
model batches the overlapping requests, so wall-clock scales far better than sequential.

This is orchestration, not a new verifier: every module still passes the exact same
byte-exact differential gate. A module that calls into another module is a known limit
(its FFI reference won't link standalone); independent modules (crc variants, codec
tables, hash families) translate cleanly.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from alchemist.verifier.build_c_dll import (
    _NONLIB_DIRS,
    discover_c_build,
    prepare_native_build,
)


@dataclass
class ModuleResult:
    module: str
    overall_pass: bool
    log_path: Path
    detail: str = ""


def _make_module_subject(root: Path, src: Path, work: Path) -> tuple[str, Path]:
    """Build a single-module subject dir mirroring the library layout: the ONE module
    `.c` plus every shared header/`.inc`, at their original relative paths."""
    mod = src.stem
    subj = work / mod
    if subj.exists():
        shutil.rmtree(subj)
    subj.mkdir(parents=True)
    rel = src.relative_to(root)
    (subj / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, subj / rel)
    for asset in list(root.rglob("*.h")) + list(root.rglob("*.inc")):
        arel = asset.relative_to(root)
        if {p.lower() for p in arel.parts[:-1]} & _NONLIB_DIRS:
            continue
        (subj / arel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, subj / arel)
    return mod, subj


def orchestrate_library(root, *, max_concurrent: int = 4, endpoint: str | None = None):
    """Translate a multi-module library module-by-module, concurrently. Returns the list of
    ModuleResult (one per library `.c`). Runs the native build once up front so generated
    sources (tables, headers) exist before the per-module subjects are cut."""
    root = Path(root)
    prepare_native_build(root)
    sources, _inc = discover_c_build(root)
    work = root / ".alchemist" / "modules"
    work.mkdir(parents=True, exist_ok=True)
    subjects = [_make_module_subject(root, s, work) for s in sources]
    # Each per-module subject needs its own stage-1 analysis; run stages 1-6 per subject.
    results: list[ModuleResult] = []
    with ThreadPoolExecutor(max_workers=max_concurrent) as ex:
        futs = {ex.submit(_run_module_full, subj, mod, endpoint): mod
                for mod, subj in subjects}
        for fut in as_completed(futs):
            results.append(fut.result())
    results.sort(key=lambda r: r.module)
    return results


def _run_module_full(subj: Path, mod: str, endpoint: str | None) -> ModuleResult:
    """Run the full pipeline (stages 1-6) on a per-module subject."""
    log_path = subj / "translate.log"
    cmd = [sys.executable, "-m", "alchemist.cli", "translate", str(subj),
           "--name", f"{mod}-rs"]
    import os as _os
    env = dict(_os.environ)
    if endpoint:
        env["ALCHEMIST_ENDPOINT"] = endpoint
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=env)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
    except subprocess.TimeoutExpired:
        out = "TIMEOUT after 900s"
    log_path.write_text(out, encoding="utf-8", errors="replace")
    ok = "OVERALL: PASS" in out
    detail = next((ln.strip() for ln in out.splitlines() if "OVERALL" in ln), "")
    return ModuleResult(module=mod, overall_pass=ok, log_path=log_path, detail=detail)
