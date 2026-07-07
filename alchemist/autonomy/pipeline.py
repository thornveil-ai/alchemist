"""Item 4 — the product surface: one command that IS the one-stop shop.

`translate_project(source)` composes every stage into a single autonomous run:

    ingest -> triage (what we can promise) -> route each in-scope fn to its builder
    -> translate + verify (differential) -> safety audit + Miri -> per-fn receipt
    -> aggregate into a signed ProjectManifest -> emit a cargo workspace

Each function goes through `translate_safely`, so one bad function degrades to a
'refused' verdict with a reason instead of killing the run. The result is an honest,
signed, buildable deliverable — not a pile of files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from alchemist.autonomy.ingest import ingest_project, scope_triage, route
from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.effect_oracle import detect_globals
from alchemist.autonomy.ownership import build_ownership_crate
from alchemist.autonomy.provenance import safety_audit, cwe_findings, VerificationReceipt
from alchemist.autonomy.packaging import (
    FunctionOutcome, ProjectManifest, translate_safely, emit_workspace,
)


def _verify_crate(res, cfile, llm, ctx, model, env, miri=False):
    """Fill -> verify -> (outcome, crate_dir). Shared tail for the wired builders."""
    from alchemist.autonomy.live_repair import make_refill, extract_rust_fn, _module_context
    from alchemist.autonomy.mechanical import mechanical_repair
    from alchemist.autonomy.diagnose import diagnose_and_fix
    from alchemist.implementer.reference_probe import extract_c_function_body
    lib = Path(res.crate_dir) / "src" / "lib.rs"
    r = make_refill(lib, cfile, llm, struct_context=ctx, temperature=0.0, on_event=lambda m: None)
    for fn in res.fill_order:
        r(fn, "Translate from the C source exactly.")

    def berr():
        return subprocess.run(["cargo", "build"], cwd=str(res.crate_dir), capture_output=True,
                              text=True, env=env).stderr

    def test():
        o = subprocess.run(["cargo", "test", "--lib"], cwd=str(res.crate_dir), capture_output=True,
                           text=True, env=env)
        out = o.stdout + o.stderr
        f = "\n".join(l for l in out.splitlines() if "error[" in l or "panic" in l)[:1200]
        return ("test result: ok" in out), f
    mechanical_repair(lib, berr)
    ok, ft = test()
    if not ok:
        for fn in reversed(res.fill_order):
            cur = extract_rust_fn(lib.read_text(), fn) or ""
            if cur:
                def ap(code, _fn=fn):
                    s = lib.read_text(); c = extract_rust_fn(s, _fn)
                    if c:
                        lib.write_text(s.replace(c, code))
                diagnose_and_fix(extract_c_function_body(cfile, fn) or "", cur, ft, llm, ap, test,
                                 max_rounds=2, context=_module_context(lib.read_text(), fn))
                mechanical_repair(lib, berr)
                ok, ft = test()
                if ok:
                    break
    miri_ok = None
    if ok and miri:
        m = subprocess.run(["cargo", "+nightly", "miri", "test", "--lib"], cwd=str(res.crate_dir),
                           capture_output=True, text=True, env=env)
        miri_ok = "test result: ok" in (m.stdout + m.stderr)
    return ok, miri_ok, lib


def translate_project(source, work, llm, env, gcc="g++", miri=False, max_fns=None):
    """Run the full pipeline over a project; return a signed ProjectManifest."""
    work = Path(work)
    proj = ingest_project(str(source), work)
    funcs, gnames = {}, set()
    for c in proj.c_files:
        txt = c.read_text(errors="replace")
        funcs.update(discover_functions(txt)); gnames |= {g.name for g in detect_globals(txt)}
    scopes = scope_triage(funcs, gnames)
    manifest = ProjectManifest(Path(str(source)).name)
    crate_dirs = []
    for i, fs in enumerate(scopes):
        if max_fns and i >= max_fns:
            break
        builder = route(fs.scope)
        if builder is None:
            manifest.add(FunctionOutcome(fs.name, "refused", reason="%s: %s" % (fs.scope, fs.reason)))
            continue
        if builder == "build_ownership_crate":
            def do(fs=fs):
                cfile = next(c for c in proj.c_files if fs.name in c.read_text(errors="replace"))
                res = build_ownership_crate([cfile.parent], work / ("out_" + fs.name), "c_" + fs.name, gcc=gcc)
                ctx = ("malloc'd buffer returned -> owned Vec<u8>; free fn takes Vec by value and drops; "
                       "NO unsafe/raw pointers.")
                ok, miri_ok, lib = _verify_crate(res, cfile, llm, ctx, "gemma-4-31b", env, miri)
                sa = safety_audit(Path(lib).read_text())
                cwes = cwe_findings(cfile.read_text())
                rec = VerificationReceipt(fs.name, "verified" if ok else "partial", res.num_vectors,
                                          1.0, sa, miri_ok, cwes, "gemma-4-31b")
                crate_dirs.append(res.crate_dir)
                return FunctionOutcome(fs.name, "verified" if ok else "partial", rec.digest(),
                                       sa.memory_safe, miri_ok, [c for c, _ in cwes])
            manifest.add(translate_safely(fs.name, do))
        else:
            manifest.add(FunctionOutcome(fs.name, "partial",
                                         reason="routable via %s (not run in this driver)" % builder))
    if crate_dirs:
        emit_workspace(work / "workspace", crate_dirs)
    return manifest
