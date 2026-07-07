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

import re
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


def _verify_crate(res, cfile, llm, ctx, model, env, miri=False, store=None, n_tries=3):
    """Fill -> verify -> (outcome, crate_dir). Shared tail for the wired builders.
    Best-of-N: up to `n_tries` sampled fills (temp climbs each retry), each gated on
    the oracle -- a borderline function the model gets right 50% of the time becomes
    ~88% at N=3. If `store` is given, retrieve worked examples into each fill and feed
    it on green (retrieval-augmented fill that compounds across the run)."""
    from alchemist.autonomy.live_repair import make_refill, extract_rust_fn, _module_context
    from alchemist.autonomy.mechanical import mechanical_repair
    from alchemist.autonomy.diagnose import diagnose_and_fix
    from alchemist.implementer.reference_probe import extract_c_function_body
    lib = Path(res.crate_dir) / "src" / "lib.rs"
    stub_src = lib.read_text()          # the unimplemented!() skeleton, restored between attempts

    def berr():
        return subprocess.run(["cargo", "build"], cwd=str(res.crate_dir), capture_output=True,
                              text=True, env=env).stderr

    def test():
        o = subprocess.run(["cargo", "test", "--lib"], cwd=str(res.crate_dir), capture_output=True,
                           text=True, env=env)
        out = o.stdout + o.stderr
        f = "\n".join(l for l in out.splitlines() if "error[" in l or "panic" in l)[:1200]
        return ("test result: ok" in out), f

    ok, ft = False, ""
    for attempt in range(n_tries):      # best-of-N: sample fills, gate EACH on the oracle
        if attempt:
            lib.write_text(stub_src)    # reset to stubs, resample
        temp = 0.0 if attempt == 0 else 0.3 + 0.2 * attempt
        r = make_refill(lib, cfile, llm, struct_context=ctx, temperature=temp, on_event=lambda m: None)
        for fn in res.fill_order:
            instr = "Translate from the C source exactly."
            if store is not None:
                ex = store.as_context(extract_c_function_body(cfile, fn) or "")
                if ex:
                    instr = ex + "\n\n" + instr
            r(fn, instr)
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
        if ok:
            break
    if ok and store is not None:                     # feed the store: every green fill teaches the next
        for fn in res.fill_order:
            cbody = extract_c_function_body(cfile, fn) or ""
            rust = extract_rust_fn(lib.read_text(), fn) or ""
            if cbody and rust:
                store.add(cbody, rust)
    miri_ok = None
    if ok and miri:
        m = subprocess.run(["cargo", "+nightly", "miri", "test", "--lib"], cwd=str(res.crate_dir),
                           capture_output=True, text=True, env=env)
        miri_ok = "test result: ok" in (m.stdout + m.stderr)
    return ok, miri_ok, lib


def _outcomes_for(fn_names, verdict, res, cfile, sa, cwes, miri_ok):
    """One receipt per translated group -> a FunctionOutcome for each fn in it."""
    rec = VerificationReceipt(",".join(sorted(fn_names)), verdict, res.num_vectors, 1.0,
                              sa, miri_ok, cwes, "gemma-4-31b")
    dig = rec.digest()
    return [FunctionOutcome(n, verdict, dig, sa.memory_safe, miri_ok, [c for c, _ in cwes])
            for n in fn_names]


def _translate_file(cfile, work, llm, env, gcc, miri, store=None):
    """Route a .c file by its dominant translatable shape, translate+verify once, and
    return {fn_name: FunctionOutcome} for the functions the chosen builder covers."""
    from alchemist.autonomy.stateful import (detect_stateful_api, resolve_typedefs,
                                             build_stateful_crate)
    from alchemist.autonomy.c_struct import resolve_c_defines
    from alchemist.autonomy.ownership import detect_heap_api
    from alchemist.autonomy.auto_translate import build_crate_from_sources
    from alchemist.autonomy.onboard import gen_fuzz_lengths
    txt = cfile.read_text(errors="replace")
    funcs = discover_functions(txt)
    stem = re.sub(r"\W", "_", cfile.stem)

    api = detect_stateful_api(funcs, resolve_c_defines(txt), resolve_typedefs(txt))
    if api:
        grp = [n for n in (api.init, api.update, api.final, *api.helpers) if n]
        res = build_stateful_crate([cfile], work / ("s_" + stem), "s_" + stem,
                                   gen_fuzz_lengths(24), gcc=gcc)
        ok, miri_ok, lib = _verify_crate(res, cfile, llm,
            "Stateful init/update/final over a ctx struct; preserve exact arithmetic.",
            "gemma-4-31b", env, miri, store)
        sa = safety_audit(Path(lib).read_text())
        return {o.function: o for o in _outcomes_for(res.fill_order or grp,
                "verified" if ok else "partial", res, cfile, sa, cwe_findings(txt), miri_ok)}, res.crate_dir if ok else None

    if detect_heap_api(funcs):
        res = build_ownership_crate([cfile], work / ("h_" + stem), "h_" + stem, gcc=gcc)
        ok, miri_ok, lib = _verify_crate(res, cfile, llm,
            "malloc'd buffer returned -> owned Vec<u8>; free fn takes Vec by value; no unsafe.",
            "gemma-4-31b", env, miri, store)
        sa = safety_audit(Path(lib).read_text())
        return {o.function: o for o in _outcomes_for(res.fill_order,
                "verified" if ok else "partial", res, cfile, sa, cwe_findings(txt), miri_ok)}, res.crate_dir if ok else None

    # scalar/buffer file: differential over each pure function build_crate_from_sources finds
    res = build_crate_from_sources([cfile], work / ("p_" + stem), "p_" + stem,
                                   [bytes(range(i)) for i in (0, 1, 8, 32, 64)], search_roots=[cfile.parent])
    ok, miri_ok, lib = _verify_crate(res, cfile, llm,
        "Pure function: buffer+len -> &[u8]; preserve arithmetic exactly.", "gemma-4-31b", env, miri, store)
    sa = safety_audit(Path(lib).read_text())
    return {o.function: o for o in _outcomes_for(res.fill_order,
            "verified" if ok else "partial", res, cfile, sa, cwe_findings(txt), miri_ok)}, res.crate_dir if ok else None


def translate_project(source, work, llm, env, gcc="g++", miri=False, max_files=None, store=None):
    """Run the full pipeline over a project (file-and-shape centric), returning a
    signed ProjectManifest. Each file is routed to the builder for its dominant
    shape; every function is triaged so out-of-scope/complex ones are refused with a
    reason. Crash-proof per file."""
    work = Path(work)
    proj = ingest_project(str(source), work)
    manifest = ProjectManifest(Path(str(source)).name)
    crate_dirs = []
    covered: set[str] = set()
    for i, cfile in enumerate(proj.c_files):
        if max_files and i >= max_files:
            break
        result = translate_safely("file:" + cfile.name,
                                  lambda cfile=cfile: _translate_file(cfile, work, llm, env, gcc, miri, store))
        if isinstance(result, tuple):
            outcomes, crate = result
            for o in outcomes.values():
                manifest.add(o); covered.add(o.function)
            if crate:
                crate_dirs.append(crate)
        elif isinstance(result, FunctionOutcome):        # the whole file crashed -> one refused note
            manifest.add(result)
    # anything the builders didn't cover -> triage-honest refusal
    for cfile in proj.c_files:
        txt = cfile.read_text(errors="replace")
        gnames = {g.name for g in detect_globals(txt)}
        for fs in scope_triage(discover_functions(txt), gnames):
            if fs.name not in covered and not any(f.function == fs.name for f in manifest.functions):
                manifest.add(FunctionOutcome(fs.name, "refused", reason="%s: %s" % (fs.scope, fs.reason)))
    if crate_dirs:
        emit_workspace(work / "workspace", crate_dirs)
    return manifest
