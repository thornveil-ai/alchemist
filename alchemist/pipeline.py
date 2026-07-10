"""Pipeline orchestrator — sequences the 6 stages, manages checkpoints."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from alchemist.analyzer.parser import CParser
from alchemist.analyzer.call_graph import CallGraphBuilder
from alchemist.analyzer.module_detector import ModuleDetector
from alchemist.config import AlchemistConfig

console = Console(force_terminal=True, legacy_windows=False)


def run_analyze(
    source: Path,
    preprocessed: bool = False,
    config: AlchemistConfig | None = None,
) -> dict:
    """Run Stage 1: Analyze a C/C++ codebase.

    Returns a dict with keys: files, call_graph, modules, summary.
    """
    config = config or AlchemistConfig()
    source = Path(source).resolve()

    if not source.is_dir():
        console.print(f"[red]Source path {source} is not a directory.[/red]")
        raise SystemExit(1)

    # Discover C/C++ files. Skip non-library trees (test/example/bench/vendor) and any
    # driver/generator that defines `int main(` — e.g. a build-time table generator — so
    # the pipeline never tries to translate `main` (which has no library semantics).
    from alchemist.verifier.build_c_dll import _MAIN_RE, _NONLIB_DIRS
    c_extensions = {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"}

    def _keep_file(f) -> bool:
        if ".git" in f.parts or "test" in f.name.lower():
            return False
        if {p.lower() for p in f.relative_to(source).parts[:-1]} & _NONLIB_DIRS:
            return False
        if f.suffix in {".c", ".cpp", ".cc", ".cxx"}:
            try:
                if _MAIN_RE.search(f.read_text(errors="replace")):
                    return False
            except OSError:
                return False
        return True

    all_files = sorted(
        f for f in source.rglob("*")
        if f.suffix in c_extensions and _keep_file(f)
    )

    # Filter to only .c and .h in the root (not contrib/test dirs for zlib)
    # Heuristic: if source has subdirs like contrib/, test/, only parse root-level files
    root_files = [f for f in all_files if f.parent == source]
    if root_files:
        parse_files = root_files
    else:
        parse_files = all_files

    console.print(f"[cyan]Analyzing {len(parse_files)} files in {source}[/cyan]")

    # Parse all files
    parser = CParser()
    parsed_files = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing C files...", total=len(parse_files))
        for f in parse_files:
            parsed = parser.parse_file(f)
            parsed_files[str(f)] = parsed
            progress.update(task, advance=1, description=f"Parsing {f.name}")

    # Build call graph
    console.print("[cyan]Building call graph...[/cyan]")
    cg_builder = CallGraphBuilder()
    call_graph = cg_builder.build(parsed_files)

    # Detect modules
    console.print("[cyan]Detecting algorithmic modules...[/cyan]")
    detector = ModuleDetector()
    modules = detector.detect(parsed_files, call_graph)

    # Module scoping (ALCHEMIST_ONLY_MODULE): translate only the named module(s)
    # of a big multi-module library while the differential ORACLE still compiles
    # the WHOLE directory (discover_c_build) so cross-module symbols resolve.
    # This is how a real cyclic library (Lua: 24 modules / 1085 fns) is translated
    # bottom-up one module at a time against a whole-library oracle, instead of
    # attempting all modules at once. Comma-separated substrings, case-insensitive.
    import os as _os
    _only = (_os.environ.get("ALCHEMIST_ONLY_MODULE") or "").strip()
    if _only:
        _wanted = [w.strip().lower() for w in _only.split(",") if w.strip()]

        def _mname(m):
            return (m.get("name", "") if isinstance(m, dict)
                    else getattr(m, "name", "")) or ""
        _kept = [m for m in modules
                 if any(w in _mname(m).lower() for w in _wanted)]
        if _kept:
            console.print(
                f"[cyan]module scope: translating {len(_kept)}/{len(modules)} "
                f"module(s) matching {_wanted} (oracle still links the whole dir)"
                f"[/cyan]")
            modules = _kept
        else:
            console.print(
                f"[yellow]ALCHEMIST_ONLY_MODULE={_only!r} matched no module; "
                f"translating all[/yellow]")

    # Function scoping (ALCHEMIST_ONLY_FNS): translate only the named functions
    # within the kept module(s). Lets the PURE surface of a real cyclic module
    # be conquered from real source (e.g. luaS_hash out of lstring's 15 fns)
    # without dragging in the VM-coupled functions that need the whole type
    # universe. Oracle still links the whole dir. Comma-separated exact/substr.
    _onlyfns = (_os.environ.get("ALCHEMIST_ONLY_FNS") or "").strip()
    if _onlyfns:
        _wf = [w.strip() for w in _onlyfns.split(",") if w.strip()]
        _wfl = {w.lower() for w in _wf}

        def _keepfn(fn):
            # EXACT match only. Substring matching drags in siblings (luaS_hash
            # would pull luaS_hashlongstr, which needs TString and breaks the
            # crate skeleton -> 0/0). List each wanted fn explicitly.
            return fn in _wf or fn.lower() in _wfl
        _tot = 0
        for m in modules:
            fns = m.get("functions", []) if isinstance(m, dict) else []
            kept = [f for f in fns if _keepfn(f)]
            if isinstance(m, dict):
                m["functions"] = kept
                fd = m.get("function_details")
                if isinstance(fd, dict):
                    m["function_details"] = {k: v for k, v in fd.items() if _keepfn(k)}
            _tot += len(kept)
        console.print(
            f"[cyan]function scope: translating {_tot} function(s) matching "
            f"{_wf} (oracle still links the whole dir)[/cyan]")

    # Build summary
    total_functions = sum(len(pf["functions"]) for pf in parsed_files.values())
    total_structs = sum(len(pf["structs"]) for pf in parsed_files.values())
    total_globals = sum(len(pf["globals"]) for pf in parsed_files.values())
    total_macros = sum(len(pf["macros"]) for pf in parsed_files.values())
    total_typedefs = sum(len(pf["typedefs"]) for pf in parsed_files.values())
    total_lines = sum(pf["line_count"] for pf in parsed_files.values())

    summary = {
        "total_files": len(parsed_files),
        "total_lines": total_lines,
        "total_functions": total_functions,
        "total_structs": total_structs,
        "total_globals": total_globals,
        "total_macros": total_macros,
        "total_typedefs": total_typedefs,
    }

    # Print summary
    console.print(f"\n  Files: {summary['total_files']}")
    console.print(f"  Lines: {summary['total_lines']:,}")
    console.print(f"  Functions: {summary['total_functions']}")
    console.print(f"  Structs: {summary['total_structs']}")
    console.print(f"  Globals: {summary['total_globals']}")
    console.print(f"  Macros: {summary['total_macros']}")
    console.print(f"  Modules detected: {len(modules)}")

    for mod in modules:
        console.print(
            f"    [yellow]{mod['name']}[/yellow] ({mod['category']}) — "
            f"{len(mod['functions'])} functions, {mod['total_lines']} lines"
        )

    return {
        "source": str(source),
        "files": {k: _serialize_parsed(v) for k, v in parsed_files.items()},
        "call_graph": call_graph,
        "modules": modules,
        "summary": summary,
    }


def _serialize_parsed(pf: dict) -> dict:
    """Make parsed file data JSON-serializable."""
    return {
        "functions": [
            {k: v for k, v in f.items() if k != "node"}
            for f in pf["functions"]
        ],
        "structs": pf["structs"],
        "globals": pf["globals"],
        "macros": pf["macros"],
        "typedefs": pf["typedefs"],
        "includes": pf["includes"],
        "line_count": pf["line_count"],
    }


# ---------------------------------------------------------------------------
# Integrated pipeline — wires every Phase C check
# ---------------------------------------------------------------------------

@dataclass
class StageOutcome:
    stage: str
    ok: bool
    summary: str = ""
    details: str = ""


@dataclass
class TranslationReport:
    workspace_dir: Path
    outcomes: list[StageOutcome] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(o.ok for o in self.outcomes)

    def add(self, outcome: StageOutcome) -> None:
        self.outcomes.append(outcome)

    def first_failure(self) -> StageOutcome | None:
        for o in self.outcomes:
            if not o.ok:
                return o
        return None

    def summary(self) -> str:
        lines = []
        for o in self.outcomes:
            mark = "PASS" if o.ok else "FAIL"
            lines.append(f"[{mark:4}] {o.stage}: {o.summary}")
        return "\n".join(lines) + "\n" + ("OVERALL: PASS" if self.ok else "OVERALL: FAIL")


def _flatten_codec_traits(arch, specs, source) -> int:
    """Drop architect-invented traits (Compressor/Decompressor/Hasher/...) whose
    methods are stateless byte codecs — buf_transform (`int f(in,inlen,out,outlen)`)
    or digest shapes. Such a function is lifted to a FREE `fn(&[u8]) -> Vec<u8>`
    (see normalize_digest_specs) and the differential harness calls it as a free
    module function (`rust_smaz_compress(&input)`). A trait wrapper
    (`fn compress(&self, ...) -> Result<usize, Self::Error>`) contradicts that on
    every axis AND the LLM architect emits it inconsistently — sometimes with a
    dangling `Self::Error` that won't even compile. Removing the trait forces the
    reliable free-function layout, making a codec translation REPRODUCIBLE instead
    of dependent on which crate design the architect happened to roll.

    Returns the number of traits dropped.
    """
    if not getattr(arch, "traits", None):
        return 0
    try:
        from alchemist.verifier.auto_config import (
            collect_subject_signatures, classify_buf_transform, classify_digest_shape,
        )
        sigs = {s.name: s for s in collect_subject_signatures(Path(source))}
    except Exception:  # noqa: BLE001
        return 0
    if not sigs:
        return 0

    def _is_codec_method(m) -> bool:
        # Map a trait method to a C signature. The method name is usually the
        # short verb (`compress`) while the C fn is prefixed (`smaz_compress`),
        # so try: exact name, C-fn-name-ends-with-method, then the fn name
        # appearing in the method's signature text.
        mname = getattr(m, "name", "") or ""
        sig = sigs.get(mname)
        if sig is None and mname:
            for nm, s in sigs.items():
                if nm == mname or nm.endswith("_" + mname) or nm.endswith(mname):
                    sig = s
                    break
        if sig is None:
            for nm, s in sigs.items():
                if nm in (getattr(m, "signature", "") or ""):
                    sig = s
                    break
        if sig is None:
            return False
        try:
            return (classify_buf_transform(sig) is not None
                    or classify_digest_shape(sig) is not None)
        except Exception:  # noqa: BLE001
            return False

    kept, dropped = [], 0
    for t in arch.traits:
        methods = getattr(t, "methods", None) or []
        if methods and all(_is_codec_method(m) for m in methods):
            dropped += 1
        else:
            kept.append(t)
    if dropped:
        arch.traits = kept
    return dropped


def _reconcile_module_placement(arch, specs) -> None:
    """Ensure every spec module is claimed by exactly one crate's `modules`.

    The skeleton keys module emission off `crate.modules` containing real
    module names. When the architect lists function names there, or leaves a
    module unclaimed, the module's functions never get emitted. This rewrites
    `modules` to reference real module names: each module stays where the
    architect put it if a crate already references one of its functions or
    its name; otherwise it lands in the best-named crate (or the first).
    Empty crates are dropped.
    """
    spec_module_names = [m.name for m in specs]
    fn_to_module = {
        a.name: m.name for m in specs for a in (m.algorithms or [])
    }
    if not spec_module_names:
        return

    # Which crate should own each module? Prefer a crate that already names
    # the module or one of its functions; fall back by name affinity.
    placement: dict[str, str] = {}
    for mod_name in spec_module_names:
        chosen = None
        for c in arch.crates:
            listed = set(c.modules or [])
            if mod_name in listed or any(
                fn_to_module.get(x) == mod_name for x in listed
            ):
                chosen = c.name
                break
        if chosen is None and arch.crates:
            # Name affinity: a crate whose name shares a token with the module.
            for c in arch.crates:
                if mod_name.lower() in c.name.lower() or c.name.lower() in mod_name.lower():
                    chosen = c.name
                    break
        if chosen is None and arch.crates:
            chosen = arch.crates[0].name
        if chosen is not None:
            placement[mod_name] = chosen

    # Rewrite every crate's module list to the real module names it owns.
    for c in arch.crates:
        c.modules = [m for m in spec_module_names if placement.get(m) == c.name]

    # Drop crates that ended up owning no modules AND declaring no types/traits
    # (a pure type/error crate legitimately has no modules).
    def _keeps(c) -> bool:
        if c.modules:
            return True
        has_types = any(e.crate == c.name for e in (arch.error_types or []))
        has_traits = any(t.crate == c.name for t in (arch.traits or []))
        # Keep if another crate depends on it, else it's dead weight.
        depended = any(
            c.name in (o.dependencies or []) for o in arch.crates if o is not c
        )
        return has_types or has_traits or depended
    arch.crates = [c for c in arch.crates if _keeps(c)]


def _reconcile_error_types(arch, specs) -> int:
    """Reconcile error-type names referenced in function return types.

    The extractor names errors freely (Result<_, HashError>); the architect
    names the crate's error enum independently (SipHashError). When a return
    type references an error the architecture never defines, rewrite it to the
    crate's canonical error type so the skeleton compiles. Returns the number
    of return types rewritten.
    """
    known = {e.name for e in (arch.error_types or [])}
    by_crate: dict[str, list[str]] = {}
    for e in (arch.error_types or []):
        by_crate.setdefault(e.crate, []).append(e.name)
    module_crate: dict[str, str] = {}
    for c in arch.crates:
        for m in (c.modules or []):
            module_crate[m] = c.name
    fixed = 0
    for module in specs:
        canonical = None
        crate = module_crate.get(module.name)
        if crate and by_crate.get(crate):
            canonical = by_crate[crate][0]
        elif arch.error_types:
            canonical = arch.error_types[0].name
        if not canonical:
            continue
        for alg in (module.algorithms or []):
            rt = alg.return_type or ""
            m = re.search(r"Result<\s*.+?,\s*([A-Za-z_]\w*)\s*>", rt)
            if m and m.group(1) not in known:
                alg.return_type = (
                    rt[:m.start(1)] + canonical + rt[m.end(1):]
                )
                fixed += 1
    return fixed


def _prune_dangling_builders(arch) -> int:
    """Drop builders whose built_type is never defined.

    The architect sometimes emits a fluent builder for a state struct it
    never actually defines (SipHasherBuilder -> SipHasher with no state
    wrapper), which references an undefined type and breaks the skeleton
    compile. A speculative builder with no backing type is dead scaffolding.
    """
    defined = {w.public_name for w in (getattr(arch, "state_wrappers", None) or [])}
    defined |= {e.name for e in (arch.error_types or [])}
    builders = getattr(arch, "builders", None) or []
    kept = [b for b in builders if b.built_type in defined]
    dropped = len(builders) - len(kept)
    arch.builders = kept
    return dropped


def run_architect_stage(
    source: Path,
    name: str,
    config: AlchemistConfig | None = None,
    *,
    enforce: bool = True,
) -> tuple[StageOutcome, "CrateArchitecture | None"]:
    """Run Stage 3 — design architecture AND validate it.

    If `enforce=True` and the validator finds any ERRORs, refuses to proceed
    and returns StageOutcome(ok=False).
    """
    from alchemist.architect.crate_designer import CrateDesigner
    from alchemist.architect.schemas import CrateArchitecture
    from alchemist.architect.validator import validate_architecture
    from alchemist.extractor.schemas import ModuleSpec

    specs_dir = source / ".alchemist" / "specs"
    if not specs_dir.exists():
        return StageOutcome(
            stage="architect",
            ok=False,
            summary=f"specs not found at {specs_dir}",
        ), None
    specs = [
        ModuleSpec.model_validate(json.loads(f.read_text(encoding="utf-8")))
        for f in sorted(specs_dir.glob("*.json"))
    ]
    # Whole-workspace type coherence: the extractor infers a Rust type per
    # parameter/field independently, fracturing one C type into several
    # incompatible Rust types (zlib ct_data → TreeElement / HuffmanNode /
    # Vec<(u16,u16)>). Unify registered types across params, fields, and
    # struct definitions BEFORE the architecture is designed or the skeleton
    # emitted, and persist the rewritten specs so Stage 4 reads coherent
    # types. Registry-only, so context-polymorphic C types (int, void*,
    # z_streamp) are never corrupted.
    analysis_path = source / ".alchemist" / "analysis.json"
    if analysis_path.exists():
        try:
            from alchemist.architect.type_unifier import unify_types
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            urep = unify_types(specs, analysis)
            if urep.rewrites or urep.field_rewrites or urep.dropped_structs:
                console.print(f"[cyan]type unifier: {urep.summary()}[/cyan]")
                # Persist every module (types + affected function modules).
                for module in specs:
                    (specs_dir / f"{module.name}.json").write_text(
                        module.model_dump_json(indent=2), encoding="utf-8"
                    )
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]type unifier skipped: {e}[/yellow]")
    # Cache-load: architecture is a one-shot LLM call that doesn't benefit
    # from re-running once the shape is stable. If architecture.json exists
    # and parses cleanly, re-use it. This also means a transient LLM hiccup
    # during architect stage doesn't nuke the whole run.
    arch_path = source / ".alchemist" / "architecture.json"
    arch: "CrateArchitecture | None" = None
    if arch_path.exists():
        try:
            arch = CrateArchitecture.model_validate_json(
                arch_path.read_text(encoding="utf-8")
            )
            console.print(
                f"[cyan]architect: cache hit at {arch_path.name} "
                f"({len(arch.crates)} crates) — skipping LLM call[/cyan]"
            )
        except Exception as e:  # noqa: BLE001
            console.print(
                f"[yellow]architect cache parse failed ({e}); "
                f"regenerating via LLM[/yellow]"
            )
            arch = None
    if arch is None:
        designer = CrateDesigner(config or AlchemistConfig())
        arch = designer.design(specs, project_name=name, source_description=str(source))

    # Post-architect trait extraction: fill in traits for compatible-signature
    # families the architect might have missed. Phase 0.5 requirement 4.
    # Dedupe by name: a cached arch may already carry traits from a prior run,
    # and extract_traits runs deterministically over the same specs, so it
    # would otherwise duplicate them on every invocation.
    from alchemist.architect.trait_extractor import extract_traits
    new_traits = extract_traits(specs, arch)
    if new_traits:
        existing_names = {t.name for t in (arch.traits or [])}
        added: list = []
        for t in new_traits:
            if t.name not in existing_names:
                added.append(t)
                existing_names.add(t.name)
        if added:
            arch.traits = list(arch.traits or []) + added
            console.print(
                f"[cyan]trait extractor: added {len(added)} trait(s): "
                f"{', '.join(t.name for t in added)}[/cyan]"
            )

    # Reconcile module placement: the skeleton emits a module's functions
    # into whichever crate lists that module in `modules`. The architect
    # (LLM-driven) sometimes lists FUNCTION names there instead of the real
    # module name, or scatters one source module's functions across several
    # crates — either way the module matches no crate and the skeleton emits
    # empty crates (0 functions). Guarantee every spec module is claimed by
    # exactly one crate; drop crates left with nothing.
    _reconcile_module_placement(arch, specs)
    n_flat = _flatten_codec_traits(arch, specs, source)
    if n_flat:
        console.print(
            f"[cyan]codec-flatten: dropped {n_flat} trait(s) wrapping stateless "
            f"byte codecs — emitting free `fn(&[u8]) -> Vec<u8>` (reproducible)[/cyan]"
        )
    n_err = _reconcile_error_types(arch, specs)
    n_bld = _prune_dangling_builders(arch)
    if n_err or n_bld:
        console.print(
            f"[cyan]architect reconcile: {n_err} error-type reference(s) "
            f"remapped, {n_bld} dangling builder(s) dropped[/cyan]"
        )
        # The error-type rewrite mutates specs (function return types) — the
        # skeleton reads specs from disk in Stage 4, so persist them.
        if n_err:
            for module in specs:
                (specs_dir / f"{module.name}.json").write_text(
                    module.model_dump_json(indent=2), encoding="utf-8"
                )

    (source / ".alchemist" / "architecture.json").write_text(
        arch.model_dump_json(indent=2), encoding="utf-8"
    )

    report = validate_architecture(arch, specs)
    details = "\n".join(str(i) for i in report.issues)
    if report.has_errors and enforce:
        return StageOutcome(
            stage="architect",
            ok=False,
            summary=f"validator rejected architecture: {report.summary()}",
            details=details,
        ), arch
    return StageOutcome(
        stage="architect",
        ok=True,
        summary=f"architecture validated: {report.summary()}",
        details=details,
    ), arch


def run_implement_stage(
    source: Path,
    output: Path,
    *,
    tdd: bool = True,
    config: AlchemistConfig | None = None,
) -> StageOutcome:
    """Run Stage 4 — generate Rust code.

    When `tdd=True` (default), uses the TDD generator with skeleton,
    test emission, per-function loop, and API completeness gate. Also
    runs the field scanner to pre-populate shared type schemas.
    """
    from alchemist.architect.field_scanner import scan_specs_for_fields
    from alchemist.architect.schemas import CrateArchitecture
    from alchemist.extractor.schemas import ModuleSpec

    specs_dir = source / ".alchemist" / "specs"
    arch_path = source / ".alchemist" / "architecture.json"
    if not arch_path.exists():
        return StageOutcome(
            stage="implement",
            ok=False,
            summary="architecture.json missing — run Stage 3 first",
        )
    specs = [
        ModuleSpec.model_validate(json.loads(f.read_text(encoding="utf-8")))
        for f in sorted(specs_dir.glob("*.json"))
    ]
    # Spec completer: merge orphan per-function specs from
    # specs/_functions/<module>/*.json into each module's algorithms list.
    # Spec extraction sometimes produces a function spec but fails to fold
    # it into the aggregated module, so the architect never sees it and
    # generated code that references the helper fails to compile.
    fn_dir = specs_dir / "_functions"
    if fn_dir.exists():
        added_total = 0
        for module in specs:
            per_fn_dir = fn_dir / module.name
            if not per_fn_dir.exists():
                continue
            present = {a.name for a in module.algorithms or []}
            new_algs = list(module.algorithms or [])
            for fn_json in sorted(per_fn_dir.glob("*.json")):
                data = json.loads(fn_json.read_text(encoding="utf-8"))
                name = data.get("name") or ""
                if not name or name in present:
                    continue
                data.setdefault("display_name", name)
                data.setdefault("description",
                                data.get("purpose") or data.get("algorithm_notes") or name)
                try:
                    from alchemist.extractor.schemas import AlgorithmSpec
                    new_algs.append(AlgorithmSpec.model_validate(data))
                    present.add(name)
                    added_total += 1
                except Exception:
                    continue
            if len(new_algs) != len(module.algorithms or []):
                module.algorithms = new_algs
        if added_total:
            console.print(
                f"[cyan]spec completer: merged {added_total} orphan function spec(s)[/cyan]"
            )
    # Normalize parameter types before generation. Fixes classes of extractor
    # drift (Vec<u8> output buffers → &mut [u8], u64 length pointers → &mut usize).
    from alchemist.extractor.normalizer import normalize_all
    specs, norm_notes = normalize_all(specs)
    if norm_notes:
        console.print(
            f"[cyan]spec normalizer: rewrote {len(norm_notes)} parameter(s)[/cyan]"
        )
    # Spec auditor: cross-check specs against the actual C source signatures.
    # Catches extractor-level errors (wrong state type, missing mutability)
    # that the normalizer's pattern rules don't reach. Auto-fixes safe cases.
    from alchemist.extractor.spec_auditor import (
        audit_all as audit_specs, apply_auto_fixes,
    )
    audit_report = audit_specs(specs, source)
    if audit_report.findings:
        console.print(
            f"[cyan]spec auditor: {audit_report.summary()}[/cyan]"
        )
        fixable = [f for f in audit_report.findings if f.auto_fix]
        if fixable:
            specs = apply_auto_fixes(specs, audit_report)
            console.print(
                f"[cyan]spec auditor: auto-fixed {len(fixable)} finding(s)[/cyan]"
            )
    # Constants auto-extractor: pull C #define / enum / static const into
    # each module's spec.constants so the skeleton can inject them as
    # `pub const` before the LLM sees the function stubs. Removes the
    # whole class of "undefined identifier" compile failures from LLM
    # referencing C constants it can't reproduce.
    try:
        from alchemist.extractor.constants_extractor import extract_from_path
        c_sources: dict[str, Path] = {
            p.stem: p for p in source.rglob("*.c")
            if "test" not in p.name.lower() and "example" not in p.name.lower()
        }
        total_consts = 0
        for module in specs:
            if module.constants:
                continue  # already populated (e.g., loaded from cache)
            c_file = c_sources.get(module.name)
            if c_file is None:
                continue
            try:
                report = extract_from_path(c_file)
                module.constants = report.extracted
                total_consts += report.count
            except Exception:  # noqa: BLE001
                continue
        if total_consts:
            console.print(
                f"[cyan]constants extractor: {total_consts} consts across "
                f"{len([m for m in specs if m.constants])} modules[/cyan]"
            )
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]constants extractor skipped: {e}[/yellow]")
    arch = CrateArchitecture.model_validate(
        json.loads(arch_path.read_text(encoding="utf-8"))
    )
    # Crate-layout fix (Phase 2): an error type referenced by a trait must live in the
    # trait's crate. Traits are the dependency root; an error defined in a downstream crate
    # is invisible to the trait -> "cannot find type Rc4Error". Reassign to the trait crate.
    try:
        _err = {e.name: e for e in arch.error_types}
        _moved = 0
        for _t in arch.traits:
            for _m in _t.methods:
                for _name, _e in _err.items():
                    if _name in (_m.signature or "") and _e.crate != _t.crate:
                        _e.crate = _t.crate
                        _moved += 1
        if _moved:
            console.print(f"[cyan]crate-layout: moved {_moved} trait-referenced error type(s) to the trait crate[/cyan]")
    except Exception as _ce:  # noqa: BLE001
        console.print(f"[yellow]crate-layout fix skipped: {_ce}[/yellow]")
    # Architect-invented state wrappers / builders emit `unimplemented!` method skeletons
    # with no C backing -> they fail the anti-stub gate. The verified C->Rust translation is
    # the free functions + the state struct; drop the OO embellishments.
    try:
        _drop = len(arch.state_wrappers) + len(arch.builders)
        if _drop:
            arch.state_wrappers = []
            arch.builders = []
            console.print(f"[cyan]crate-layout: dropped {_drop} unfilled wrapper/builder skeleton(s)[/cyan]")
    except Exception:  # noqa: BLE001
        pass
    # Architect sometimes gives an error variant a payload of an UNDEFINED type — e.g.
    # `NmeaError::CoreError(ChecksumError)` where ChecksumError is never defined -> E0425 and
    # the whole crate fails to compile. Strip variant fields that name a bare type nothing
    # defines (not another error type, not a primitive/std path); a variant left with no
    # fields is a valid unit variant. These enums are usually dead (the fn returns a plain
    # value), so this only removes a dangling reference, never real behaviour.
    try:
        import re as _re
        _defined = {e.name for e in arch.error_types} | {
            s.name for s in (getattr(arch, "shared_types", None) or [])}
        _prims = {
            "String", "str", "Vec", "Box", "u8", "u16", "u32", "u64", "u128", "usize",
            "i8", "i16", "i32", "i64", "i128", "isize", "bool", "char", "f32", "f64", "()",
        }

        def _resolvable(f: str) -> bool:
            base = _re.split(r"[<&\s(]", f.strip(), 1)[0].strip()
            return (not base) or ("::" in base) or (base in _defined) or (base in _prims)
        _stripped = 0
        for _e in arch.error_types:
            for _v in _e.variants:
                _keep = [f for f in _v.fields if _resolvable(f)]
                if len(_keep) != len(_v.fields):
                    _stripped += len(_v.fields) - len(_keep)
                    _v.fields = _keep
        if _stripped:
            console.print(f"[cyan]crate-layout: stripped {_stripped} error-variant field(s) of undefined types[/cyan]")
    except Exception:  # noqa: BLE001
        pass
    # Architect over-designs an INFALLIBLE module (every spec fn returns a plain value) into a
    # fallible trait/error hierarchy — `trait X { fn ..->Result<_, Self::Error> }`, a nested
    # error enum across crates — that nothing fills and that breaks the build differently each
    # run (undefined Self::Error, cross-crate error refs, malformed method sigs). If NO function
    # in the spec is fallible, drop the invented traits + error types so the crate is just the
    # verified free functions. Fallible modules (rc4's Result<_, Rc4Error>) keep their design.
    try:
        _rets = [(getattr(al, "return_type", "") or "")
                 for m in specs for al in (getattr(m, "algorithms", None) or [])]
        _fallible = any(("Result" in r) or ("Error" in r) for r in _rets)
        if _rets and not _fallible and (arch.traits or arch.error_types):
            _n = len(arch.traits) + len(arch.error_types)
            arch.traits = []
            arch.error_types = []
            console.print(f"[cyan]crate-layout: dropped {_n} trait/error over-design(s) for an infallible module[/cyan]")
    except Exception:  # noqa: BLE001
        pass

    # Field scanner: pre-populate shared-type field schemas.
    # The scanner's output is available to the TDD generator via the
    # ModuleSpec.shared_types list (augmented below).
    field_schemas = scan_specs_for_fields(specs, arch)
    if field_schemas:
        console.print(
            f"[cyan]field scanner: {len(field_schemas)} type schemas pre-scanned[/cyan]"
        )

    # Auto-oracle (Phase 1): synthesize test vectors from the compiled C reference for any
    # differentiable function lacking standards KATs, so the fill loop can verify arbitrary
    # cold code -- the C itself is the oracle, not a hardcoded catalog.
    try:
        from alchemist.verifier.auto_config import normalize_byte_buffer_types
        _nb = normalize_byte_buffer_types(source, specs)
        if _nb:
            console.print(f"[cyan]type-lift: {_nb} char*+len param(s) -> &[u8] (byte buffer, not &str)[/cyan]")
    except Exception as _e:  # noqa: BLE001
        console.print(f"[yellow]byte-buffer type-lift skipped: {_e}[/yellow]")
    # Digest-shape spec normalization (SipHash/SHA family): the generic lifter turns
    # `int f(const in*, inlen, out*, outlen)` into `f(&[u8], &mut [u8]) -> Result<(), E>`,
    # which mismatches the digest differential adapter AND (being fallible) invites the
    # architect to wrap a one-shot hash in a Hasher trait + error hierarchy. Rewrite it to
    # the shape the digest oracle expects: `f(data: &[u8]) -> Vec<u8>` (RETURNS the digest).
    try:
        from alchemist.verifier.auto_config import normalize_digest_specs
        _nd = normalize_digest_specs(source, specs)
        if _nd:
            console.print(f"[cyan]digest-lift: {_nd} hash fn(s) -> `fn(&[u8]) -> Vec<u8>` (returns the digest)[/cyan]")
    except Exception as _e:  # noqa: BLE001
        console.print(f"[yellow]digest type-lift skipped: {_e}[/yellow]")
    # Struct-carry (Phase 2): emit the safe state struct into the crate so stateful code
    # compiles cold (kills "cannot find type Rc4State"); C struct is the source of truth.
    # First make single-scalar state consistent across functions — the extractor sometimes
    # keeps the struct name (`&mut FnvState`) and sometimes unwraps to the primitive
    # (`&mut u32`) for the SAME state, breaking state sharing + leaving the struct undefined.
    try:
        from alchemist.verifier.struct_lift import normalize_single_scalar_state
        _nn = normalize_single_scalar_state(source, specs)
        if _nn:
            console.print(f"[cyan]state-normalize: unified {_nn} single-scalar state param(s)[/cyan]")
    except Exception as _e:  # noqa: BLE001
        console.print(f"[yellow]state-normalize skipped: {_e}[/yellow]")
    try:
        from alchemist.verifier.struct_lift import inject_state_shared_types
        _ns = inject_state_shared_types(source, specs)
        if _ns:
            console.print(f"[cyan]struct-carry: emitted {_ns} state struct(s) into the crate[/cyan]")
    except Exception as _e:  # noqa: BLE001
        console.print(f"[yellow]struct-carry skipped: {_e}[/yellow]")
    try:
        from alchemist.verifier.auto_config import synthesize_c_vectors
        _nv = synthesize_c_vectors(source, specs)
        if _nv:
            console.print(f"[cyan]auto-oracle: synthesized C-reference vectors for {_nv} function(s)[/cyan]")
    except Exception as _e:  # noqa: BLE001
        console.print(f"[yellow]auto-oracle skipped: {_e}[/yellow]")

    if tdd:
        from alchemist.implementer.tdd_generator import TDDGenerator
        gen = TDDGenerator(config=config)
        result = gen.generate_workspace(specs, arch, output, source_root=source)
        ok = bool(result.ok)
        summary = (
            f"TDD: {sum(1 for a in result.attempts if a.tests_passed)}/"
            f"{len(result.attempts)} fns pass tests; "
            f"API {'ok' if result.api_report and result.api_report.ok else 'incomplete'}"
        )
        return StageOutcome(stage="implement", ok=ok, summary=summary)
    else:
        from alchemist.implementer.code_generator import CodeGenerator
        gen = CodeGenerator(config=config)
        results = gen.generate_workspace(specs, arch, output)
        ok = all(r.get("success") for r in results.values()) if results else False
        return StageOutcome(
            stage="implement", ok=ok,
            summary=f"compiled {sum(1 for r in results.values() if r.get('success'))}/{len(results)} crates",
        )


def run_verify_stage(
    c_source_dir: Path,
    output: Path,
    diff_config=None,
    *,
    refuse_without_diff: bool = True,
) -> StageOutcome:
    """Run Stage 5 — mandatory differential verification gate.

    When diff_config is None and refuse_without_diff=True (the production
    default), the differential gate FAILS with reason 'no config'. This
    enforces the 'refuse success without verification' rule.

    Specs are loaded from `<c_source_dir>/.alchemist/specs` when present so
    the semantic gate (family lints, wrong-variant detection) runs; a subject
    without specs skips that gate but can still never pass overall without a
    differential config.
    """
    from alchemist.verifier.differential_tester import verify_workspace

    specs = None
    specs_error = None
    if (Path(c_source_dir) / ".alchemist" / "specs").is_dir():
        try:
            from alchemist.solo import _load_specs_and_arch
            specs, _arch, _out = _load_specs_and_arch(Path(c_source_dir))
        except Exception as e:  # noqa: BLE001
            # The subject HAS specs but they can't be read — that must fail
            # the semantic gate, not silently disarm it.
            specs_error = str(e)
            console.print(
                f"[yellow]verify: could not load specs for semantic gate: {e}[/yellow]"
            )
    if diff_config is None and specs:
        # No curated config for this subject — derive one from its headers
        # and specs (subject-compiled oracle, recognized checksum shapes).
        # None back means nothing was configurable and the differential
        # gate refuses, which is the correct fail-closed outcome.
        from alchemist.verifier.auto_config import build_diff_config
        diff_config = build_diff_config(Path(c_source_dir), specs)
        if diff_config is not None:
            console.print(
                f"[cyan]verify: auto-generated differential config — "
                f"{len(diff_config.harnesses)} harness(es), oracle from "
                f"{len(diff_config.c_sources)} C source file(s)[/cyan]"
            )
    report = verify_workspace(
        output, diff_config=diff_config, specs=specs, specs_error=specs_error,
        refuse_without_diff=refuse_without_diff,
    )
    ok = report.passed
    first = report.first_failure
    summary = "all gates PASS" if ok else (
        f"gate {first.name} FAILED: {first.summary}" if first else "unknown failure"
    )
    return StageOutcome(stage="verify", ok=ok, summary=summary)


def run_translate_all(
    source: Path,
    name: str,
    output: Path | None = None,
    *,
    config: AlchemistConfig | None = None,
    stages: tuple[int, int] = (1, 6),
    diff_config=None,
    enforce_validator: bool = True,
    refuse_without_diff: bool = True,
) -> TranslationReport:
    """Integrated `alchemist translate` flow.

    Wires in every Phase C gate:
      * Stage 3 validator (refuses to proceed on errors if enforce_validator).
      * Stage 4 field scanner + TDD generator + API completeness.
      * Stage 5 mandatory differential gate (refuses success if diff_config
        is missing, when refuse_without_diff=True).

    Returns a TranslationReport whose `.ok` field is True only if EVERY
    stage passed.
    """
    config = config or AlchemistConfig()
    source = Path(source).resolve()
    checkpoint = source / ".alchemist"
    checkpoint.mkdir(parents=True, exist_ok=True)
    out = output or (checkpoint / "output")
    report = TranslationReport(workspace_dir=out)

    # Phase 0 Bug #8: workspace mutex. Two concurrent pipelines on the
    # same subject race on output/, wins/, and target/. Acquire an
    # advisory lock; fail loudly if another live process holds it.
    from alchemist.workspace_lock import workspace_lock, WorkspaceLockError
    try:
        _lock_cm = workspace_lock(source, timeout=10.0)
        _lock_cm.__enter__()
    except WorkspaceLockError as e:
        report.add(StageOutcome(
            stage="lock", ok=False,
            summary=f"workspace lock acquisition failed: {e}",
        ))
        return report

    try:
        return _run_translate_all_locked(
            source, name, out, checkpoint, report, config,
            stages, diff_config, enforce_validator, refuse_without_diff,
        )
    finally:
        try:
            _lock_cm.__exit__(None, None, None)
        except Exception:
            pass


def _run_translate_all_locked(
    source: Path,
    name: str,
    out: Path,
    checkpoint: Path,
    report,
    config,
    stages: tuple[int, int],
    diff_config,
    enforce_validator: bool,
    refuse_without_diff: bool,
):
    """Body of run_translate_all, executed under workspace_lock."""
    start_stage, end_stage = stages

    # --- Stage 1: Analyze ---
    if start_stage <= 1 <= end_stage:
        try:
            analysis = run_analyze(source, config=config)
            (checkpoint / "analysis.json").write_text(
                json.dumps(analysis, indent=2, default=str), encoding="utf-8"
            )
            report.add(StageOutcome(
                stage="analyze", ok=True,
                summary=(
                    f"{analysis['summary']['total_files']} files, "
                    f"{analysis['summary']['total_functions']} fns, "
                    f"{len(analysis['modules'])} modules"
                ),
            ))
        except SystemExit as e:
            report.add(StageOutcome(
                stage="analyze", ok=False, summary=f"failed: {e}"
            ))
            return report

    # --- Stage 2: Extract ---
    if start_stage <= 2 <= end_stage:
        from alchemist.extractor.spec_extractor import SpecExtractor
        from alchemist.extractor.spec_validator import validate_specs as _validate_specs
        from alchemist.extractor.variant_resolver import (
            make_llm_tiebreaker,
            resolve_specs,
        )
        from alchemist.extractor.schemas import ModuleSpec
        from alchemist.llm.client import AlchemistLLM

        specs_dir = checkpoint / "specs"
        specs_dir.mkdir(exist_ok=True)
        try:
            analysis_data = json.loads((checkpoint / "analysis.json").read_text(encoding="utf-8"))
            extractor = SpecExtractor(config=config)
            specs = extractor.extract_all(analysis_data, output_dir=specs_dir)
        except Exception as e:
            report.add(StageOutcome(stage="extract", ok=False, summary=f"extract failed: {e}"))
            return report

        # Variant disambiguation — resolve multi-variant families (CRC, AES, SHA)
        # to a single canonical variant BEFORE implementation sees the spec.
        try:
            llm = AlchemistLLM(config)
            tiebreaker = make_llm_tiebreaker(llm)
            resolutions = resolve_specs(specs, llm_tiebreaker=tiebreaker)
            resolved_count = sum(1 for r in resolutions if r.resolved)
            ambiguous_unresolved = [r for r in resolutions if not r.resolved and r.candidates]
            if resolved_count:
                console.print(
                    f"[cyan]variant resolver: resolved {resolved_count} algorithms; "
                    f"{len(ambiguous_unresolved)} unresolved[/cyan]"
                )
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]variant resolver skipped: {e}[/yellow]")

        # Re-save specs after resolution since apply_resolution mutates them
        for s in specs:
            (specs_dir / f"{s.name}.json").write_text(
                s.model_dump_json(indent=2), encoding="utf-8"
            )

        # Spec validator — second-pass plausibility check.
        val_report = _validate_specs(specs)
        msg = val_report.summary()
        if not val_report.ok:
            msg += " — errors: " + "; ".join(i.message for i in val_report.errors[:3])
            report.add(StageOutcome(stage="extract", ok=False, summary=msg))
            return report
        report.add(StageOutcome(stage="extract", ok=True, summary=msg))

    # --- Stage 3: Architect (w/ validator gate) ---
    if start_stage <= 3 <= end_stage:
        outcome, arch = run_architect_stage(
            source, name, config=config, enforce=enforce_validator,
        )
        report.add(outcome)
        if not outcome.ok:
            return report

    # --- Stage 4: Implement (field scanner + TDD) ---
    if start_stage <= 4 <= end_stage:
        outcome = run_implement_stage(source, out, tdd=True, config=config)
        report.add(outcome)
        if not outcome.ok:
            return report

    # --- Stage 5: Verify (mandatory differential gate) ---
    if start_stage <= 5 <= end_stage:
        # Auto-select a diff_config based on subject name when caller
        # didn't supply one. zlib has a pre-built config; other subjects
        # will gain configs as they're added (mbedTLS, lwIP, ...).
        resolved_diff_config = diff_config
        if resolved_diff_config is None:
            subject_name = source.name.lower()
            if "zlib" in subject_name:
                from alchemist.verifier.zlib_config import zlib_diff_config
                resolved_diff_config = zlib_diff_config(c_source_dir=source)
                console.print(
                    "[cyan]Stage 5: auto-selected zlib differential config[/cyan]"
                )
        outcome = run_verify_stage(
            source, out,
            diff_config=resolved_diff_config,
            refuse_without_diff=refuse_without_diff,
        )
        report.add(outcome)
        if not outcome.ok:
            return report

    # --- Stage 6: Report ---
    if start_stage <= 6 <= end_stage:
        try:
            from alchemist.reporter.metrics import MetricsCollector
            collector = MetricsCollector(out, source)
            metrics = collector.collect_all()
            (out / "alchemist-report.json").write_text(
                json.dumps(metrics, indent=2, default=str), encoding="utf-8"
            )
            report.add(StageOutcome(stage="report", ok=True, summary="metrics written"))
        except Exception as e:
            report.add(StageOutcome(stage="report", ok=False, summary=f"report gen failed: {e}"))

    return report
