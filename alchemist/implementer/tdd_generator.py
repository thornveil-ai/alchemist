"""Phase 4C: test-driven code generation.

Orchestration:

    Phase A (skeleton)         — emit compile-ready types + `unimplemented!()`
                                  bodies, confirm `cargo check --workspace`.
    Phase B (tests)            — append test blocks sourced from
                                  spec.test_vectors + standards catalog.
                                  `cargo check` must still pass (tests compile).
                                  `cargo test` is expected to FAIL (stubs panic).
    Phase C (per-fn fill-in)   — for each algorithm, in dependency order:
        * Ask the LLM for an implementation of just that function.
        * Deterministically scrub + reject if the result trips the anti-stub
          detector. Re-prompt with stricter instructions.
        * Run the test(s) for that function. If they pass, move on; otherwise
          re-prompt with the test failure output as supervisor signal.
        * After N failing iterations, escalate to the holistic fixer.
    Phase D (completeness gate)— verify every spec.source_functions has a
                                  `pub fn`. Re-prompt if missing.

The rewritten `CodeGenerator.generate_workspace` in the sibling module
`code_generator.py` delegates to this when `tdd_mode=True`.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from alchemist.architect.schemas import CrateArchitecture, CrateSpec
from alchemist.config import AlchemistConfig
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec
from alchemist.implementer.anti_stub import ScanReport, scan_text
from alchemist.implementer.semantic_lints import (
    has_errors as _semantic_has_errors,
    lint_function as _semantic_lint,
    summarize_for_reprompt as _semantic_summary,
)
from alchemist.implementer.api_completeness import (
    ApiCompletenessReport,
    check_workspace as check_api,
    missing_to_reprompt_context,
)
from alchemist.implementer.init_templates import try_init_template
from alchemist.implementer.scrubber import scrub_rust
from alchemist.implementer.skeleton import (
    WorkspaceSkeletonResult,
    generate_workspace_skeleton,
    _topo_sort,
    _run_cargo_check,
    _sanitize_param_name,
)
from alchemist.implementer.test_generator import generate_tests_for_workspace
from alchemist.llm.client import AlchemistLLM, CachedContext

console = Console(force_terminal=True, legacy_windows=False)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class FunctionAttempt:
    algorithm: str
    crate: str
    module: str
    iterations: int = 0
    final_compiled: bool = False
    tests_passed: bool = False
    escalated_to_holistic: bool = False
    escalated_to_decomposition: bool = False
    last_error: str = ""
    # P0.14 telemetry: wall-clock and model spend for THIS function's fill, so
    # slow/expensive functions are visible and budgets can be set. A cached-win
    # restore reads as elapsed>0 but llm_calls==0 — the cheapest outcome.
    elapsed_s: float = 0.0
    llm_calls: int = 0
    output_tokens: int = 0
    # P0.6 escalation-ladder audit: which tier actually PRODUCED the win —
    # "cached" | "single" | "multi_sample" | "holistic" | "decomposition", or ""
    # if refused. Aggregated across a corpus this proves each tier earns its
    # budget (a tier with zero wins is dead weight or a rare safety net).
    won_via: str = ""


@dataclass
class TDDResult:
    workspace_dir: Path
    skeleton: WorkspaceSkeletonResult | None = None
    attempts: list[FunctionAttempt] = field(default_factory=list)
    api_report: ApiCompletenessReport | None = None
    workspace_compiles: bool = False
    workspace_tests_passed: bool = False
    final_stdout: str = ""
    final_stderr: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.workspace_compiles
            and self.workspace_tests_passed
            and (self.api_report.ok if self.api_report else True)
        )


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert Rust systems engineer translating C algorithms
into idiomatic safe Rust. You will be given a precise specification for a
single function and must produce ONLY the Rust source for that one function
(or a drop-in replacement of its body). Your output MUST satisfy:

  1. Implement the ACTUAL algorithm described by the spec — no stubs, no
     simulation, no "we don't have the algorithm" comments, no placeholders.
  2. Use only safe Rust. No `unsafe` blocks unless the spec explicitly says
     unsafe is required.
  3. No markdown fences. No explanation. Return ONLY valid Rust.
  4. Match the exact function signature from the spec.
  5. Assume `extern crate alloc;` is in scope when the crate is `no_std`.
"""

_IMPL_PROMPT = """Implement this single Rust function. Do NOT stub, simulate, or
write scaffolding that compiles but doesn't work. Implement the actual
algorithm described by the spec.

## Algorithm spec
Name: {name}
Category: {category}
Description: {description}
Mathematical notes: {math}
Referenced standards: {standards}

## Signature (must match exactly)
```rust
{signature}
```

## Inputs
{inputs}

## Return type
{return_type}

## Invariants / preconditions
{invariants}

## Known test vectors (your implementation MUST satisfy these)
{test_vectors}

## Standards catalog vectors (authoritative, MUST satisfy)
{catalog_vectors}
{reference_impls}
{idiom_patterns}

## Shared type definitions (already in scope via `use zlib_types::*;`)
{struct_context}

## Error type variants IN SCOPE (construct these with the EXACT shape shown)
{error_context}

## Module-level constants/statics IN SCOPE (you may reference these by name)
{available_consts}

If a lookup table / dictionary / codebook is listed above as in scope, you
MUST reference it by that exact name. Do NOT redefine it, do NOT fabricate
your own version of it, and do NOT invent placeholder entries — the real
table is already declared for you and any hand-written substitute WILL be
wrong. (The most common failure here is re-typing a translation dictionary
from memory; never do that when the const is already in scope.)

Any lookup table, precomputed array, or cached value the C code kept in a
file-scope `static` that is NOT listed above does NOT exist in this
translation. Do not reference an undefined module constant — compute the
data you need inside your function body (e.g. build a CRC table from its
polynomial at the top of the function). C initializer functions (e.g.
`*_init_table`) and their `ready`-flag statics have no safe-Rust
equivalent; never call them.

## Current stub to replace
```rust
{current_body}
```
{previous_failure}

Return the COMPLETE function definition (signature + body) that replaces
the stub. Adapt the reference implementation (if provided) to match the
signature required above. Return ONLY the function — no const/static/use
declarations, no markdown, no explanation.
"""


# ---------------------------------------------------------------------------
# TDD generator
# ---------------------------------------------------------------------------

def _repair_skeleton_undefined_types(output_dir: Path, stderr: str, *, rounds: int = 3):
    """Deterministic skeleton compile-repair gate (P1.5 flakiness fix).

    The MODEL designs the crate/trait/error-type architecture, and does so
    NON-DETERMINISTICALLY: it routinely references TYPES it never defines ("cannot find
    type X" — in an error-enum variant like `UrlError(UrlParseError)`, a trait signature,
    a builder, anywhere). A DIFFERENT set of invented types appears on each run, so patching
    the emitters one error-site at a time never converges, and a single undefined type
    aborts the whole run at 0/0. This gate parses the compiler's "cannot find type X"
    diagnostics, injects a `pub struct X;` placeholder into the erroring crate's lib.rs, and
    re-checks — up to `rounds` times. Placeholders make the crate compile; any function that
    actually depends on an invented type fails its differential and is honestly refused
    (fail-closed). Returns (ok, final_stderr). Fixes the CLASS, wherever it appears."""
    out = Path(output_dir)
    _DEF = re.compile(r"\b(?:struct|enum|type|trait|union)\s+{}\b")
    for _ in range(rounds):
        by_lib: dict[Path, set[str]] = {}
        for m in re.finditer(
                r"cannot find type `([A-Za-z_]\w*)`[^\n]*\n\s*-->\s*([^\s:]+):", stderr):
            tname, relpath = m.group(1), m.group(2).strip()
            by_lib.setdefault(out / relpath, set()).add(tname)
        if not by_lib:
            return False, stderr  # errors we don't know how to repair deterministically
        changed = False
        for lib, names in by_lib.items():
            if not lib.exists():
                continue
            txt = lib.read_text(encoding="utf-8")
            add = [f"#[derive(Debug, Clone, PartialEq, Eq)]\npub struct {n};"
                   for n in sorted(names)
                   if not re.search(_DEF.pattern.format(re.escape(n)), txt)]
            if add:
                lib.write_text(
                    txt + "\n\n// --- skeleton-repair: placeholders for architect-invented "
                    "types (fail-closed) ---\n" + "\n".join(add) + "\n", encoding="utf-8")
                changed = True
        if not changed:
            return False, stderr
        ok, stderr = _run_cargo_check(out, timeout=300)
        if ok:
            return True, stderr
    return False, stderr


class TDDGenerator:
    def __init__(
        self,
        config: AlchemistConfig | None = None,
        llm: AlchemistLLM | None = None,
        *,
        max_iter_per_fn: int = 5,
        holistic_after: int = 3,
        multi_sample_after: int = 2,
        multi_sample_n: int = 6,
        multi_sample_temperature: float = 0.35,
        per_fn_budget_s: float = 900.0,
    ):
        self.config = config or AlchemistConfig()
        self.llm = llm or AlchemistLLM(self.config)
        self.max_iter_per_fn = max_iter_per_fn
        self.holistic_after = holistic_after
        self.multi_sample_after = multi_sample_after
        self.multi_sample_n = multi_sample_n
        self.multi_sample_temperature = multi_sample_temperature
        # Per-function WALL-CLOCK budget. The fill loop was iteration-bounded only (5
        # iters × 6-way multi-sample × holistic ×3 = ~35–40 model calls), with NO time
        # cap — so a single hard function (parse_url_char's goto state machine) could
        # grind ~20 min, and a handful of them made a whole http-parser run take ~90 min.
        # A wall-clock cap lets easy functions pass fast and bounds the hard ones to an
        # honest refusal, keeping runs (and experiments/model-A-Bs) tractable. Env-tunable.
        import os as _os0
        self.per_fn_budget_s = float(
            _os0.environ.get("ALCHEMIST_PER_FN_BUDGET_S", per_fn_budget_s))
        # P0.13 deterministic replay: with ALCHEMIST_DETERMINISTIC set, decode
        # greedily everywhere (temp 0) and collapse the multi-sample fan-out to a
        # single greedy sample, so the same subject + fixed fuzz seed reproduces
        # byte-identical Rust across runs. Off by default (sampling finds more wins).
        import os as _os
        self._deterministic = bool(_os.environ.get("ALCHEMIST_DETERMINISTIC"))
        if self._deterministic:
            self.multi_sample_temperature = 0.0
            self.multi_sample_n = 1

    # --- Main entry ---

    def generate_workspace(
        self,
        specs: list[ModuleSpec],
        architecture: CrateArchitecture,
        output_dir: Path,
        *,
        source_root: Path | None = None,
    ) -> TDDResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        result = TDDResult(workspace_dir=output_dir)
        # Remember the source root so the reference probe can locate
        # C function bodies for transliteration. Probe silently skips
        # if source_root is None.
        self._source_root = source_root
        self._probe_refs: dict = {}
        self._probe_attempted: set[str] = set()
        # Error enum definitions, so the fill prompt can tell the model the
        # exact variant shapes it constructs (InvalidKeyLength(usize), not a
        # unit variant). Without this the model guesses the arity and hits
        # E0308 constructing Err(...).
        self._error_types = list(architecture.error_types or [])

        # Phase A: skeleton
        console.print("[bold cyan]TDD Phase A: skeleton generation[/bold cyan]")
        skel = generate_workspace_skeleton(specs, architecture, output_dir, cargo_check=True)
        result.skeleton = skel
        if not skel.ok:
            # Skeleton compile-repair gate: the architect is non-deterministic and often
            # references invented types it never defines. Rather than abort the whole run
            # (0/0), inject placeholders for those undefined types and re-check. This is the
            # durable fix for the run-to-run flakiness (per-error emitter patches don't
            # converge). If repair fails, fall through to the honest abort below.
            _rep_ok, _rep_stderr = _repair_skeleton_undefined_types(
                output_dir, skel.workspace_stderr)
            if _rep_ok:
                console.print("[green]skeleton-repair: injected placeholders for "
                              "architect-invented types → skeleton now compiles[/green]")
                skel.ok = True
            else:
                console.print(f"[red]skeleton failed to compile (repair insufficient):\n"
                              f"{_rep_stderr[:2000]}[/red]")
                result.workspace_compiles = False
                return result

        # Phase B: tests (append test blocks)
        console.print("[bold cyan]TDD Phase B: test emission[/bold cyan]")
        # Fuzz-vector backfill: for every algorithm without extracted vectors
        # AND without catalog vectors, try to synthesize vectors by calling
        # the C reference library. Closes the P2 loophole where functions
        # with no vectors would silently compile-only-pass. Vectors persist
        # into the spec checkpoints (with oracle provenance tags) when the
        # source root is known.
        self._backfill_fuzz_vectors(
            specs,
            specs_dir=(source_root / ".alchemist" / "specs")
            if source_root else None,
        )
        test_results = generate_tests_for_workspace(specs, architecture, output_dir)
        total_tests = sum(t.tests_written for t in test_results)
        console.print(f"  emitted {total_tests} tests across {len(test_results)} crates")

        # Verify tests COMPILE (even if they fail)
        ok, stderr = _run_cargo_check(output_dir, timeout=300)
        if not ok:
            # Re-run with --all-targets to surface test compile errors
            ok_at, stderr_at = _run_cargo_all_targets(output_dir)
            if not ok_at:
                console.print(f"[red]test block compile failed:\n{stderr_at[:2000]}[/red]")
                result.workspace_compiles = False
                return result

        # Phase C: per-function TDD
        console.print("[bold cyan]TDD Phase C: per-function implementation loop[/bold cyan]")
        self._workspace_dir = output_dir  # for struct context lookup
        self._cached_ctx = self.llm.create_cached_context(
            system_text=_SYSTEM_PROMPT,
            project_context=self._build_project_context(specs, architecture),
        )
        # Reference probe is lazy: synthesized per-function during Phase C
        # when (a) the function has no curated ref AND (b) the first
        # generation iteration failed. This avoids spending 50+ min up-front
        # probing every function when most succeed without a probe-generated
        # template. See self._ensure_probe_ref in _fill_in_function.
        for crate_name in _topo_sort(architecture):
            crate_spec = next((c for c in architecture.crates if c.name == crate_name), None)
            if not crate_spec:
                continue
            crate_modules = [m for m in specs if m.name in set(crate_spec.modules)]
            for module in crate_modules:
                # Topologically sort algorithms within the module so leaf
                # functions are generated before wrappers. A wrapper like
                # `compress` depends on `deflate` compiling correctly; if we
                # generate wrappers first, they fail because the leaves are
                # still `unimplemented!()` stubs.
                ordered_algs = self._topo_sort_algorithms(module.algorithms)
                for alg in ordered_algs:
                    # P0.14: measure wall-clock + model spend per function. Tolerant
                    # of an LLM shim without a `.stats` dict (test fakes) — telemetry
                    # is diagnostic and must never break a fill.
                    def _usage():
                        s = getattr(self.llm, "stats", None)
                        if isinstance(s, dict):
                            return s.get("call_count", 0), s.get("total_output_tokens", 0)
                        return 0, 0
                    _t0 = time.perf_counter()
                    _c0, _o0 = _usage()
                    attempt = self._fill_in_function(
                        alg, module, crate_spec, specs, architecture, output_dir,
                    )
                    _c1, _o1 = _usage()
                    attempt.elapsed_s = round(time.perf_counter() - _t0, 3)
                    attempt.llm_calls = _c1 - _c0
                    attempt.output_tokens = _o1 - _o0
                    result.attempts.append(attempt)
                    # Compile-isolation (crate-level verified-core + honest-refusal-tail):
                    # a refused function's last (broken/non-compiling) body must NOT stay in
                    # the crate — it fails compilation and blocks EVERY subsequently-filled
                    # sibling from verifying (jsmn_parse's type error was dragging down the
                    # correct jsmn_init). Reset it to a compiling unimplemented!() stub so
                    # the functions the model CAN translate still compile + verify.
                    if not attempt.tests_passed:
                        try:
                            self._stub_refused_fn(alg, module, crate_spec, output_dir)
                        except Exception:  # noqa: BLE001
                            pass

        # Phase D: API completeness
        console.print("[bold cyan]TDD Phase D: API completeness check[/bold cyan]")
        api = check_api(specs, architecture, output_dir)
        result.api_report = api
        if not api.ok:
            # Attempt a targeted fix: re-prompt for each missing
            self._fix_missing(api, specs, architecture, output_dir)
            api = check_api(specs, architecture, output_dir)
            result.api_report = api

        # Final: workspace-wide cargo test
        console.print("[bold cyan]TDD final: cargo test --workspace[/bold cyan]")
        tests_ok, tout, terr = _run_cargo_test(output_dir)
        result.final_stdout = tout
        result.final_stderr = terr
        result.workspace_tests_passed = tests_ok

        check_ok, _ = _run_cargo_check(output_dir, timeout=300)
        result.workspace_compiles = check_ok

        return result

    # --- Phase C helpers ---

    def _wins_cache_path(
        self, workspace_dir: Path, crate: str, module: str, fn_name: str,
    ) -> Path:
        # Anchor the wins cache to the SUBJECT (source root), not to
        # workspace_dir.parent. With an EXTERNAL --output (e.g. /tmp/xxx) the old
        # .parent anchor pointed at the shared temp ROOT, so every subject wrote to
        # one /tmp/wins keyed only by crate/module/fn — non-deterministic across
        # --output locations, cross-subject collision-prone, and it silently made
        # the leaf benchmark NOT cold (prior-run wins short-circuited fills, so the
        # "first-pass" number was mostly cached restores). The subject dir is stable
        # regardless of --output and is exactly what run_leafbench's _clean_state
        # clears, so a cleaned run is genuinely cold. (P0.4)
        root = getattr(self, "_source_root", None)
        if root is not None:
            base = Path(root) / ".alchemist" / "wins"
        else:
            # Legacy fallback for callers that don't pass source_root (regen/solo
            # paths where workspace_dir is subject/.alchemist/output, so .parent is
            # already subject/.alchemist — the same location, kept stable).
            base = workspace_dir.parent / "wins"
        return base / crate / module / f"{fn_name}.rs"

    def _hardport_path(
        self, subject_hint: str, crate: str, module: str, fn_name: str,
    ) -> Path | None:
        """Locate a hand-port for (subject, crate, module, fn) if one exists.

        Hand-ports live in-package at
          alchemist/references/impls/<subject>_hardports/<crate>/<module>/<fn>.rs

        Subject hint is derived from the workspace name or crate prefix —
        e.g., "zlib" for crate "zlib-checksum". Returns None if no match.
        """
        from alchemist.references import registry as _reg
        from alchemist.implementer.skeleton import _snake
        base = _reg.REFERENCES_DIR
        # Try subject-specific hardports dir. Spec algorithm names can carry
        # display punctuation ("main (inftrees.c generator)") while hardport
        # files use the emitted Rust fn name — try both.
        names = [fn_name]
        snaked = _snake(fn_name)
        if snaked != fn_name:
            names.append(snaked)
        for key in (subject_hint, crate.split("-", 1)[0]):
            if not key:
                continue
            for name in names:
                p = base / f"{key}_hardports" / crate / module / f"{name}.rs"
                if p.exists():
                    return p
        return None

    def _load_cached_win(
        self, workspace_dir: Path, crate: str, module: str, fn_name: str,
    ) -> str | None:
        """Return the Rust body text to try first for this fn.

        Priority:
          1. Hand-port (alchemist/references/impls/<subject>_hardports/...)
             — authored by humans, versioned with the package, always up to date.
          2. Workspace wins cache (<workspace>/.alchemist/wins/...)
             — LLM-produced wins from prior runs of THIS subject.
        """
        subject_hint = workspace_dir.parent.parent.name if workspace_dir else ""
        hardport = self._hardport_path(subject_hint, crate, module, fn_name)
        if hardport is not None:
            try:
                return hardport.read_text(encoding="utf-8")
            except Exception:
                pass
        p = self._wins_cache_path(workspace_dir, crate, module, fn_name)
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def _save_cached_win(
        self, workspace_dir: Path, crate: str, module: str, fn_name: str,
        fn_body: str,
    ) -> None:
        """Persist a verified-winning impl to the cache.

        Previously swallowed all exceptions silently — disk full, perms,
        or path issues would silently stop the cache from accumulating.
        Now: log + re-raise on failure, with round-trip verify to catch
        partial writes.
        """
        p = self._wins_cache_path(workspace_dir, crate, module, fn_name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(fn_body, encoding="utf-8")
        # Round-trip verify: the wins cache is load-bearing for monotonic
        # progress. A silently-truncated write means next-run cache restore
        # fails → iterate → maybe-regress. Loud failure is better.
        readback = p.read_text(encoding="utf-8")
        if readback != fn_body:
            raise RuntimeError(
                f"wins cache write verify FAILED: {p} "
                f"(wrote {len(fn_body)} bytes, read back {len(readback)})"
            )

    def _verify_cached_win_twice(
        self, crate_dir: Path, test_name_prefix: str | list[str],
    ) -> tuple[bool, int]:
        """Run the test filter twice. Returns (ok, total_tests_observed).

        A cached win that passes once but fails once is flaky — caching
        it pollutes the cache and poisons later runs. Require 2-for-2.
        """
        total_tests = 0
        for attempt_idx in range(2):
            ok, tout, terr = _run_cargo_test_filter(crate_dir, test_name_prefix)
            combined = (tout or "") + "\n" + (terr or "")
            import re as _re
            ran_counts = [int(m) for m in _re.findall(
                r"running\s+(\d+)\s+tests?", combined
            )]
            if not ok or not any(n > 0 for n in ran_counts):
                return False, total_tests
            total_tests = max(total_tests, sum(ran_counts))
        return True, total_tests

    def _trace_fill(self, alg, crate, module, iteration, kind, content):
        """Env-gated per-iteration fill trace (P0.1). When ALCHEMIST_FILL_TRACE
        names a directory, write the model's Rust, the compile error, and the
        differential divergence for every iteration to
        <dir>/<crate>__<module>__<fn>/iterNN.<kind> — so root-causing a fill no
        longer requires hand-instrumenting this file. No-op when unset; never
        raises."""
        import os
        base = os.environ.get("ALCHEMIST_FILL_TRACE")
        if not base:
            return
        try:
            slug = f"{crate}__{module}__{alg.name}".replace("/", "_").replace("\\", "_")
            d = Path(base) / slug
            d.mkdir(parents=True, exist_ok=True)
            (d / f"iter{iteration:02d}.{kind}").write_text(content or "", encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    def _fill_in_function(
        self,
        alg: AlgorithmSpec,
        module: ModuleSpec,
        crate_spec: CrateSpec,
        all_specs: list[ModuleSpec],
        arch: CrateArchitecture,
        workspace_dir: Path,
    ) -> FunctionAttempt:
        crate_dir = workspace_dir / crate_spec.name
        module_path = crate_dir / "src" / f"{module.name}.rs"
        attempt = FunctionAttempt(
            algorithm=alg.name, crate=crate_spec.name, module=module.name,
        )
        if not module_path.exists():
            attempt.last_error = f"module file missing: {module_path}"
            return attempt

        # Wins cache fast-path: if a prior run got this function passing,
        # try that impl first. If it still compiles + tests pass under the
        # current skeleton/spec, take the win with zero LLM calls. Honest
        # because the test suite still runs and verifies correctness.
        cached_win = self._load_cached_win(
            workspace_dir, crate_spec.name, module.name, alg.name,
        )
        if cached_win:
            current = module_path.read_text(encoding="utf-8")
            replaced = self._replace_fn_in_source(current, alg.name, cached_win)
            if replaced:
                module_path.write_text(replaced, encoding="utf-8")
                ok_compile, _ = _run_cargo_check(crate_dir, timeout=180)
                if ok_compile:
                    test_name_prefix = _test_filters_for_fn(alg.name)
                    # 2x verify at restore: a flaky cached impl poisons
                    # progress. Both runs must pass with >0 tests observed.
                    ok_twice, total_tests = self._verify_cached_win_twice(
                        crate_dir, test_name_prefix,
                    )
                    if ok_twice and total_tests > 0:
                        attempt.iterations = 0
                        attempt.final_compiled = True
                        attempt.tests_passed = True
                        attempt.won_via = "cached"
                        console.print(
                            f"  [green]{alg.name}: cached win restored "
                            f"(0 LLM calls, 2x verified, {total_tests} tests)[/green]"
                        )
                        return attempt
                # Cached win didn't hold — revert and fall through to iteration
                module_path.write_text(current, encoding="utf-8")

        # No-op static-table initializer: a zero-input void function whose
        # only C effect was filling a file-scope static. In safe Rust that
        # global doesn't exist and each consumer computes its own table, so
        # the correct COMPLETE translation is an empty body. There is nothing
        # to verify (no inputs, no observable output) — accept on compile.
        from alchemist.implementer.init_templates import (
            noop_table_init_template, free_noop_template,
        )
        noop_init = noop_table_init_template(alg)
        # A pure free/destroy wrapper (C body is only deallocation calls) is a
        # no-op in safe Rust — owned buffers drop automatically. Same accept-on-
        # compile path as the static-table no-op; body-confirmed, so fail-closed.
        if noop_init is None:
            noop_init = free_noop_template(alg, getattr(self, "_source_root", None))
        if noop_init:
            current = module_path.read_text(encoding="utf-8")
            replaced = self._replace_fn_in_source(current, alg.name, noop_init)
            if replaced:
                module_path.write_text(replaced, encoding="utf-8")
                ok_compile, _ = _run_cargo_check(crate_dir, timeout=180)
                if ok_compile:
                    attempt.iterations = 0
                    attempt.final_compiled = True
                    attempt.tests_passed = True
                    attempt.won_via = "template"
                    try:
                        self._save_cached_win(
                            workspace_dir, crate_spec.name, module.name,
                            alg.name, noop_init,
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    console.print(
                        f"  [green]{alg.name}: static-table initializer → "
                        f"no-op (safe-Rust has no mutable global)[/green]"
                    )
                    return attempt
                module_path.write_text(current, encoding="utf-8")

        # Short-circuit: if the function has no verifiable test vectors
        # upfront, skip iteration entirely. Iterating would burn LLM calls
        # on code we can't verify. P2 surfaces the gap rather than silently
        # accepting it.
        from alchemist.standards import lookup_test_vectors
        has_spec_vectors = bool(alg.test_vectors)
        has_catalog_vectors = bool(lookup_test_vectors(alg.name))
        if not has_spec_vectors and not has_catalog_vectors:
            attempt.last_error = (
                "no verifiable test vectors — add spec.test_vectors, extend "
                "fuzz_vectors bindings, or add to standards catalog"
            )
            console.print(
                f"  [red]{alg.name}: no test vectors — skipping (cannot verify)[/red]"
            )
            return attempt

        test_name_prefix = _test_filters_for_fn(alg.name)
        fallback_test = f"smoke_{alg.name}"
        previous_failure = ""  # carries test output into next iteration prompt

        # Fast path: deterministic template for init/reset functions.
        # These fail LLM generation consistently — bypass the loop.
        # CRITICAL: we still run the correctness test after the template
        # lands. Per P2, a template compiling is not a correctness proof.
        # If tests exist and pass, great. If no tests exist, fall back to
        # the compile-only accept (init fns with no observable output
        # cannot be verified without state-mutator bindings).
        template_code = try_init_template(alg)
        if template_code:
            current = module_path.read_text(encoding="utf-8")
            replaced = self._replace_fn_in_source(current, alg.name, template_code)
            if replaced:
                module_path.write_text(replaced, encoding="utf-8")
                ok_compile, _err = _run_cargo_check(crate_dir, timeout=180)
                if ok_compile:
                    # Run the test filter to see if we have real tests
                    ok_test, tout, terr = _run_cargo_test_filter(
                        crate_dir, test_name_prefix,
                    )
                    combined = tout + "\n" + terr
                    import re as _re
                    ran_counts = [int(m) for m in _re.findall(
                        r"running\s+(\d+)\s+tests?", combined
                    )]
                    had_real_tests = any(n > 0 for n in ran_counts)
                    if ok_test and had_real_tests:
                        # 2x verify before caching — one flaky pass
                        # poisons next-run restore
                        ok_twice, _ = self._verify_cached_win_twice(
                            crate_dir, test_name_prefix,
                        )
                        if not ok_twice:
                            console.print(
                                f"  [yellow]{alg.name}: init template passed once "
                                f"but not twice — treating as iter fail[/yellow]"
                            )
                            module_path.write_text(current, encoding="utf-8")
                        else:
                            attempt.iterations = 0
                            attempt.final_compiled = True
                            attempt.tests_passed = True
                            attempt.won_via = "template"
                            try:
                                self._save_cached_win(
                                    workspace_dir, crate_spec.name, module.name,
                                    alg.name, template_code,
                                )
                            except Exception as e:  # noqa: BLE001
                                console.print(
                                    f"  [red]{alg.name}: cache save failed: {e}[/red]"
                                )
                            console.print(
                                f"  [green]{alg.name}: init template + 2x tests pass[/green]"
                            )
                            return attempt
                    if not ok_test:
                        # Template compiled but tests failed — revert and
                        # let LLM iteration take over
                        module_path.write_text(current, encoding="utf-8")
                    elif had_real_tests:
                        # Tests passed (unreachable — already handled above)
                        pass
                    else:
                        # No tests exist. Template is a tombstone. Keep it
                        # but mark the attempt as failed: P2 forbids compile-
                        # only pass.
                        attempt.last_error = (
                            "init template accepted but no tests exist to "
                            "verify correctness (P2 forbids compile-only pass)"
                        )
                        console.print(
                            f"  [yellow]{alg.name}: init template landed but unverified[/yellow]"
                        )
                        return attempt
                else:
                    # Template didn't compile — revert and fall through to LLM
                    module_path.write_text(current, encoding="utf-8")

        # Const-table carry: EMIT any lookup table(s) the C body reads as Rust `const`
        # arrays into the crate module, so the model REFERENCES them by name instead of
        # re-typing hundreds of values (which it can't do reliably — the #1 cause of
        # compile-but-diverge on table-driven CRC/hash code).
        try:
            _src_root = getattr(self, "_source_root", None)
            if _src_root:
                from alchemist.implementer.reference_probe import (
                    extract_c_function_body, extract_referenced_arrays,
                    extract_referenced_string_arrays,
                    c_array_to_rust_const, c_string_array_to_rust_const,
                )
                from alchemist.verifier.build_c_dll import discover_c_build as _disc2
                _cf_all, _cf_inc = _disc2(_src_root)
                _cur = module_path.read_text(encoding="utf-8")
                _consts = []
                for _cf in _cf_all:
                    _b = extract_c_function_body(_cf, alg.name)
                    if not _b:
                        continue
                    for _arr in extract_referenced_arrays(_cf, _b, include_dirs=_cf_inc):
                        _conv = c_array_to_rust_const(_arr)
                        if _conv and f"const {_conv[0]}:" not in _cur:
                            _consts.append(_conv[1])
                    # Byte-string lookup tables (a codec's codebook: char* NAME[N] = {"...", ...})
                    # -> Rust `[&[u8]; N]`, so the model references it instead of retyping
                    # hundreds of escape-laden entries. Byte-exact; the differential re-checks it.
                    for _sarr in extract_referenced_string_arrays(_cf, _b, include_dirs=_cf_inc):
                        _sconv = c_string_array_to_rust_const(_sarr)
                        if _sconv and f"const {_sconv[0]}:" not in _cur:
                            _consts.append(_sconv[1])
                    break
                if _consts:
                    module_path.write_text(
                        _cur.rstrip() + "\n\n" + "\n".join(_consts) + "\n",
                        encoding="utf-8")
                    console.print(f"  [cyan]{alg.name}: carried {len(_consts)} lookup table(s) "
                                  f"into the crate[/cyan]")
        except Exception:  # noqa: BLE001
            pass

        # Freeze the skeleton's parameter count BEFORE the fill loop. The loop may rewrite
        # alg.inputs to match the model's returned signature (idiomatic param drift), which
        # would defeat the arity guard — it would end up comparing the drifted signature
        # against itself. The pre-generated differential tests are built for THIS arity.
        _orig_arity = len(alg.inputs or [])
        import time as _time
        _fn_deadline = _time.monotonic() + self.per_fn_budget_s
        for iteration in range(1, self.max_iter_per_fn + 1):
            # Wall-clock budget: a hard function that keeps failing must not grind the
            # whole run. Once over budget, stop iterating and let it refuse (fail-closed).
            if iteration > 1 and _time.monotonic() > _fn_deadline:
                console.print(
                    f"  [yellow]{alg.name}: per-function budget "
                    f"({self.per_fn_budget_s:.0f}s) exceeded at iter {iteration} — "
                    f"stopping fill; honest refusal[/yellow]")
                break
            attempt.iterations = iteration
            current = module_path.read_text(encoding="utf-8")
            current_body = self._extract_fn_body(current, alg.name)

            # Multi-sample fan-out at iteration >= multi_sample_after.
            # If sampling finds a compile+test-pass candidate, take the win.
            if iteration >= self.multi_sample_after:
                ms = self._multi_sample_attempt(
                    alg, module_path, current, current_body or "unimplemented!()",
                    previous_failure=previous_failure, crate_dir=crate_dir,
                    test_name_prefix=test_name_prefix,
                )
                # A multi-sample win requires BOTH zero failures AND at
                # least one passing test. Otherwise cargo's "0 passed; 0
                # failed" success counts as a win even when no test
                # actually ran — the same P2 loophole as the main loop.
                if (
                    ms is not None and ms.ok and ms.best
                    and ms.best.tests_failed == 0
                    and ms.best.tests_passed >= 1
                ):
                    # 2x verify the multi-sample winner before declaring
                    # success. ms's evaluator only tested once per candidate.
                    ok_twice, _ = self._verify_cached_win_twice(
                        crate_dir, test_name_prefix,
                    )
                    if not ok_twice:
                        console.print(
                            f"  [yellow]{alg.name}: multi-sample passed once "
                            f"but not twice — iter continues[/yellow]"
                        )
                        continue
                    attempt.final_compiled = True
                    attempt.tests_passed = True
                    attempt.won_via = "multi_sample"
                    # Snapshot the winning FULL fn item (signature + body) from
                    # the module file. Prior bug: saved body-only, which the
                    # splice guard (5cf38f3) then rejects at restore time,
                    # making the cache entry unusable. Save full fn instead.
                    try:
                        final_src = module_path.read_text(encoding="utf-8")
                        m = self._find_fn(final_src, alg.name)
                        final_fn = (
                            final_src[m["item_start"]:m["item_end"]]
                            if m else None
                        )
                        if final_fn:
                            self._save_cached_win(
                                workspace_dir, crate_spec.name, module.name,
                                alg.name, final_fn,
                            )
                    except Exception as e:  # noqa: BLE001
                        console.print(
                            f"  [red]{alg.name}: cache save failed: {e}[/red]"
                        )
                    console.print(
                        f"  [green]{alg.name}: multi-sample win on iter {iteration} "
                        f"(candidate #{ms.best.candidate_idx})[/green]"
                    )
                    return attempt

            # Generate replacement (context-aware: includes prev failure).
            # Strip the #[cfg(test)] module: as more functions in a module
            # fill, the accumulated test bodies balloon the file (zlib-trees
            # hit 220KB / 112 tests), overflowing the model's context window
            # and yielding an empty completion. The model needs the sibling
            # signatures + consts, never the test bodies.
            new_fn = self._prompt_for_impl(
                alg, current_body or "unimplemented!()",
                previous_failure=previous_failure,
                module_source=self._strip_test_module(
                    module_path.read_text(encoding="utf-8")),
            )
            if not new_fn:
                attempt.last_error = "LLM returned empty"
                continue

            # Deterministic cleanup
            new_fn, _ = scrub_rust(new_fn)

            # Strip leaked module-level items (use/static/const) the LLM
            # may have emitted above the function definition.
            new_fn = self._strip_module_items(new_fn)
            self._trace_fill(alg, crate_spec.name, module.name, iteration, "rust", new_fn)

            # Anti-stub check
            stub_violations = scan_text("pending.rs", new_fn)
            if stub_violations:
                violation_summary = "; ".join(
                    f"{v.pattern}: {v.snippet.strip()[:80]}" for v in stub_violations[:3]
                )
                previous_failure = (
                    f"## Previous iteration was REJECTED as a stub.\n\n"
                    f"You wrote:\n```rust\n{new_fn[:1500]}\n```\n\n"
                    f"Rejection reasons: {violation_summary}\n\n"
                    f"Write REAL working code. No unimplemented!(), no todo!(), "
                    f"no 'for this spec we simulate' comments, no empty Ok(()) "
                    f"bodies. Implement the actual algorithm."
                )
                console.print(f"  [yellow]{alg.name}: anti-stub rejected iteration {iteration}[/yellow]")
                continue

            # Arity guard: the fill MUST keep the skeleton's parameter count. Idiomatic
            # param drift (the model adding/removing a length or capacity argument) silently
            # breaks the pre-generated differential tests, which are built for the spec
            # signature — a whole class of stateful failures. Reject + re-prompt explicitly.
            _exp_arity = _orig_arity
            _sig_m = re.search(r"\bfn\s+" + re.escape(alg.name) + r"\s*\(([^)]*)\)", new_fn)
            if _sig_m is not None and _exp_arity > 0:
                _got_arity = len([x for x in _sig_m.group(1).split(",") if x.strip()])
                if _got_arity != _exp_arity:
                    _want = ", ".join(
                        f"{_sanitize_param_name(i.name, k)}: {i.rust_type}"
                        for k, i in enumerate(alg.inputs or []))
                    previous_failure = (
                        "## Previous iteration CHANGED the function signature (rejected).\n\n"
                        f"You wrote a signature with {_got_arity} parameter(s); the required "
                        f"signature has EXACTLY {_exp_arity}:\n"
                        f"```rust\npub fn {alg.name}({_want}) ...\n```\n\n"
                        "Keep this signature EXACTLY — do NOT add, remove, or reorder "
                        "parameters. Fill only the body. If the C used a separate length/"
                        "capacity argument, derive it from a slice parameter's .len()."
                    )
                    console.print(
                        f"  [yellow]{alg.name}: arity guard rejected iter {iteration} "
                        f"({_got_arity} params vs {_exp_arity})[/yellow]"
                    )
                    continue

            # Semantic lint (family-specific invariants) — reject early if
            # the candidate clearly violates its algorithm's math, so we
            # don't burn a cargo check/test cycle on it.
            semantic_findings = _semantic_lint(new_fn, alg)
            if _semantic_has_errors(semantic_findings):
                previous_failure = (
                    f"## Previous iteration was REJECTED by the semantic linter.\n\n"
                    f"You wrote:\n```rust\n{new_fn[:2500]}\n```\n\n"
                    f"Lint findings:\n{_semantic_summary(semantic_findings)}\n\n"
                    f"These are algorithm correctness issues, not syntax. Check "
                    f"your constants, polynomials, and endianness against the "
                    f"referenced standards."
                )
                console.print(
                    f"  [yellow]{alg.name}: semantic lint rejected iter {iteration} — "
                    f"{len([f for f in semantic_findings if f.severity == 'error'])} errors[/yellow]"
                )
                continue

            # Splice into module
            replaced = self._replace_fn_in_source(current, alg.name, new_fn)
            if not replaced:
                attempt.last_error = f"could not splice new body for fn {alg.name}"
                continue
            module_path.write_text(replaced, encoding="utf-8")

            # Compile check (crate only)
            ok_compile, cerr = _run_cargo_check(crate_dir, timeout=180)
            if not ok_compile:
                # Deterministic mechanical repair BEFORE re-prompting: apply
                # rustc's own machine-applicable suggestions (as-usize coercions,
                # missing `mut`, unused imports) via cargo fix. The model
                # routinely writes algorithmically-correct code that fails only
                # on a trivial coercion the LLM repair loop can't reliably fix;
                # rustfix resolves these deterministically. Correctness is still
                # gated by the byte-exact differential below, so this can only
                # rescue a mechanically-broken CORRECT body, never mask a wrong
                # algorithm.
                if _run_cargo_fix(crate_dir, timeout=180):
                    ok_fixed, cerr_fixed = _run_cargo_check(crate_dir, timeout=180)
                    if ok_fixed:
                        console.print(
                            f"  [green]{alg.name}: cargo fix repaired mechanical "
                            f"compile error(s) on iter {iteration}[/green]"
                        )
                        ok_compile, cerr = True, cerr_fixed
            if not ok_compile:
                # Revert and try again with compile-error context + the
                # LLM's own failed attempt so it can see what it wrote.
                # Without the attempt in context, the next prompt shows the
                # reverted stub (unimplemented!()) and the LLM can't tell
                # which of its choices broke — it just rewrites similar code.
                module_path.write_text(current, encoding="utf-8")
                attempt.last_error = _top_lines(cerr, 3)
                self._trace_fill(alg, crate_spec.name, module.name, iteration, "compile", cerr)
                previous_failure = (
                    f"## Previous iteration FAILED to compile.\n\n"
                    f"You wrote this:\n```rust\n{new_fn[:2500]}\n```\n\n"
                    f"Cargo error output:\n```\n{_top_lines(cerr, 40)}\n```\n\n"
                    f"Fix the specific compile errors above. Do NOT rewrite from "
                    f"scratch — identify the offending fields/types/imports and "
                    f"correct only those. Keep the overall algorithm the same. "
                    f"Pay special attention to: field names on struct params, "
                    f"import paths, and type mismatches."
                )
                console.print(f"  [yellow]{alg.name}: compile failed, reverting (iter {iteration})[/yellow]")
                # After iter 1's compile failure, synthesize a reference from
                # the C source and make it available for iter 2+. The probe
                # runs only once per algorithm per run — this is the lazy
                # generalization primitive.
                if iteration == 1:
                    self._ensure_probe_ref(alg)
                continue

            attempt.final_compiled = True

            # Run tests that match the function name
            ok_test, tout, terr = _run_cargo_test_filter(
                crate_dir, test_name_prefix,
            )
            combined = (tout or "") + "\n" + (terr or "")
            # Cargo returns exit 0 even when ZERO tests matched the filter.
            # Detect that case explicitly: if the output shows "0 passed; 0
            # failed" WITHOUT any "running N tests" line reporting N>0, then
            # no tests ran. Per P2 (no compile-only pass) we must fail here
            # rather than claim success.
            import re as _re
            ran_counts = [int(m) for m in _re.findall(
                r"running\s+(\d+)\s+tests?", combined
            )]
            had_real_tests = any(n > 0 for n in ran_counts)
            if ok_test and had_real_tests:
                # 2x verify before caching — prevents flaky passes from
                # polluting the cache. Both runs must return ok + >0 tests.
                ok_twice, _ = self._verify_cached_win_twice(
                    crate_dir, test_name_prefix,
                )
                if not ok_twice:
                    console.print(
                        f"  [yellow]{alg.name}: iter {iteration} passed once "
                        f"but not twice — iter continues[/yellow]"
                    )
                    continue
                attempt.tests_passed = True
                # Attribute the win: if the holistic fixer already ran in a prior
                # iteration, its multi-file repair set up this convergence; else
                # it's a plain single-sample fill/repair.
                attempt.won_via = "holistic" if attempt.escalated_to_holistic else "single"
                # Persist the winning body so the next run skips iteration
                # for this function (huge accumulation effect across runs).
                if new_fn:
                    try:
                        self._save_cached_win(
                            workspace_dir, crate_spec.name, module.name,
                            alg.name, new_fn,
                        )
                    except Exception as e:  # noqa: BLE001
                        console.print(
                            f"  [red]{alg.name}: cache save failed: {e}[/red]"
                        )
                console.print(f"  [green]{alg.name}: tests pass on iter {iteration} (2x verified)[/green]")
                return attempt

            # No tests matched this function's prefix — P2 violation to
            # accept. Mark as failed so the user sees which functions are
            # unverifiable. Fuzz-vector backfill already ran; if it produced
            # nothing, no amount of retry will help — the only path forward
            # is to extend fuzz bindings. Break out of the iteration loop
            # instead of burning LLM calls we cannot verify.
            if ok_test and not had_real_tests:
                attempt.last_error = (
                    "no correctness test available for this function; "
                    "compile-only acceptance is forbidden by the "
                    "zero-shortcut policy"
                )
                console.print(
                    f"  [red]{alg.name}: no test vectors — cannot verify correctness[/red]"
                )
                return attempt

            attempt.last_error = _top_lines(terr, 5)
            _combined_out = (tout or "") + chr(10) + (terr or "")
            _divergence = _distill_vector_divergence(_combined_out)
            self._trace_fill(
                alg, crate_spec.name, module.name, iteration, "test",
                (("DIVERGENCE: " + _divergence + "\n\n") if _divergence else "")
                + _combined_out,
            )
            previous_failure = (
                f"## Previous iteration compiled but FAILED tests.\n\n"
                f"You wrote:\n```rust\n{new_fn[:2500]}\n```\n\n"
                + (_divergence + "\n" if _divergence else "")
                + f"Test output:\n```\n{_top_lines(_combined_out, 40)}\n```\n\n"
                f"The code compiles but produces wrong output. Check the "
                f"expected values in the test and fix the algorithm logic. "
                f"Most likely causes: off-by-one, wrong initial state, "
                f"wrong constant, incorrect bit ordering."
            )
            console.print(f"  [yellow]{alg.name}: tests failed on iter {iteration}[/yellow]")

            # Escalate to holistic
            if iteration >= self.holistic_after and iteration < self.max_iter_per_fn:
                attempt.escalated_to_holistic = True
                self._holistic_fix(crate_dir, alg, attempt.last_error)

        # Refusal-time escalation: verifier-policed structural decomposition.
        # The whole fill loop refused this function. Try to break it into
        # smaller helpers via a gcc-PROVEN byte-exact C split, then translate
        # the (easier) decomposed unit and re-verify with the SAME differential
        # test. Fail-closed: an unproven split is discarded and a failed
        # translation reverts — so this can only convert refusals into wins,
        # never degrade a passing function.
        if not attempt.tests_passed:
            try:
                if self._attempt_structural_decomposition(
                    alg, module, crate_spec, module_path, crate_dir,
                    workspace_dir, test_name_prefix,
                ):
                    attempt.final_compiled = True
                    attempt.tests_passed = True
                    attempt.escalated_to_decomposition = True
                    attempt.won_via = "decomposition"
            except Exception as e:  # noqa: BLE001
                console.print(
                    f"  [yellow]{alg.name}: structural-decomposition "
                    f"escalation error (non-fatal): {e}[/yellow]"
                )

        return attempt

    def _error_context_for(self, alg: AlgorithmSpec) -> str:
        """List the variants of any error enum this function's return type
        references, so the model constructs them with the right arity."""
        error_types = getattr(self, "_error_types", None) or []
        if not error_types:
            return "(no error enums in scope)"
        rt = alg.return_type or ""
        referenced = {e.name for e in error_types if e.name in rt}
        # If the return type doesn't name a known error, show them all —
        # the model may still reference one.
        show = [e for e in error_types if not referenced or e.name in referenced]
        lines: list[str] = []
        for e in show:
            variants = []
            for v in e.variants:
                if not v.fields:
                    variants.append(v.name)
                elif any(":" in f for f in v.fields):
                    fields = ", ".join(
                        f if ":" in f else f"f{i}: {f}"
                        for i, f in enumerate(v.fields))
                    variants.append(f"{v.name} {{ {fields} }}")
                else:
                    variants.append(f"{v.name}({', '.join(v.fields)})")
            lines.append(f"enum {e.name} {{ {'; '.join(variants)} }}")
        return "\n".join(lines) if lines else "(no error enums in scope)"

    @staticmethod
    def _strip_test_module(src: str) -> str:
        """Remove the trailing `#[cfg(test)] mod tests { ... }` block.

        Accumulated test bodies dominate a filled module's size (zlib-trees:
        220KB, 112 tests) and overflow the model's context window on the next
        fill. The fill needs sibling signatures and consts, never the tests.
        Brace-matched removal so code after the block (rare) is preserved.
        """
        m = re.search(r"#\[cfg\(test\)\]\s*\n\s*mod\s+tests\s*\{", src)
        if not m:
            return src
        i = m.end() - 1  # at the opening brace
        depth = 0
        for j in range(i, len(src)):
            c = src[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return src[:m.start()] + src[j + 1:]
        return src[:m.start()]  # unbalanced — drop to EOF

    @staticmethod
    def _consts_in_scope(module_source: str | None) -> str:
        """List module-level const/static identifiers the fill may reference.

        The model otherwise invents plausible names (CRC32_TABLE) for data
        that a C file-scope static held but that was never materialized in
        the safe-Rust module — an undefined-name compile error every
        iteration. Telling it exactly what IS in scope makes it either use
        the real const (zlib injects CRC32_TABLE) or compute locally
        (tinychk computes its table at runtime, so nothing is listed).
        """
        if not module_source:
            return "(none — compute any lookup data inside your function)"
        names: list[str] = []
        # Match ANY const/static identifier, not just SCREAMING_CASE. Carried
        # C tables keep their source name (e.g. `Smaz_cb`, `Smaz_rcb`), which
        # is mixed-case; a caps-only pattern misses them, so the model is told
        # nothing is in scope and HALLUCINATES its own (wrong) lookup table.
        for m in re.finditer(
            r"^\s*(?:pub\s+)?(?:const|static)\s+(?:mut\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:",
            module_source, re.MULTILINE,
        ):
            if m.group(1) not in names:
                names.append(m.group(1))
        if not names:
            return "(none — compute any lookup data inside your function)"
        return ", ".join(names)

    def _prompt_for_impl(
        self, alg: AlgorithmSpec, current_body: str, *,
        previous_failure: str = "",
        temperature: float = 0.15,
        module_source: str | None = None,
    ) -> str | None:
        # P0.13: greedy decode in deterministic-replay mode.
        if getattr(self, "_deterministic", False):
            temperature = 0.0
        from alchemist.standards import lookup_test_vectors
        from alchemist.references import find_references
        from alchemist.references.registry import references_for_standards
        schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        }
        params = "\n".join(
            f"- {_sanitize_param_name(p.name, k)}: {p.rust_type}  — {p.description}"
            for k, p in enumerate(alg.inputs)
        ) or "(no inputs)"
        # Render extracted vectors compactly. `rust_body` vectors ARE whole
        # Rust test functions (with large state literals — a single
        # gen_bitlen vector can be ~7KB); dumping them all overflowed the
        # model's context and it returned empty. They are verification
        # artifacts, not prompt material, so summarize rather than inline.
        _tv = alg.test_vectors or []
        _rust_body = [v for v in _tv if (v.tolerance or "") == "rust_body"]
        _plain = [v for v in _tv if (v.tolerance or "") != "rust_body"]
        _lines = [
            f"- inputs={v.inputs} → expected={v.expected_output}  ({v.description})"
            for v in _plain
        ]
        if _rust_body:
            # Inline the SHORT, single-line rust_body assertions (str_lookup string
            # tables, scalar checks) so the model COPIES the known expected outputs
            # instead of GUESSING them from memory. This was the load-bearing scaffolding
            # bug: http_method_str's exact GET/POST/... table lives in these vectors, but
            # they were summarized away, so the model had to reproduce a library's string
            # table from memory against a hidden oracle — impossible for ANY model. Long
            # multi-line rust_body test functions (tree-builders) stay SUMMARIZED to avoid
            # the context overflow that originally motivated dropping them.
            _short = [(v.expected_output or "").strip() for v in _rust_body
                      if "\n" not in (v.expected_output or "")
                      and len(v.expected_output or "") <= 200]
            if _short:
                _lines.append(
                    "- These EXACT differential assertions MUST ALL pass — reproduce "
                    "these outputs precisely; copy the literal values, do not guess:")
                _lines.extend(f"    {s}" for s in _short)
            _long = len(_rust_body) - len(_short)
            if _long:
                _lines.append(
                    f"- (+{_long} further differential tests verify this function "
                    "byte-for-byte; write the faithful algorithm and they will pass)")
        tvecs = "\n".join(_lines) or "(no extracted vectors — ensure the implementation matches the referenced standards)"
        if len(tvecs) > 9000:  # raised from 6000 so a full lookup table (e.g. ~60 HTTP
            # status strings) isn't truncated mid-table — losing entries = the model
            # guesses the rest, defeating the whole point of inlining them.
            tvecs = tvecs[:9000] + "\n- … (further vectors omitted)"
        # Standards catalog vectors (authoritative)
        catalog = lookup_test_vectors(alg.name) or []
        catalog_vec_text = "\n".join(
            f"- {v.name}: input={v.input_hex or '(empty)'} → expected={v.expected_hex}"
            for v in catalog[:5]
        ) or "(no catalog entry for this algorithm)"
        prev_failure_section = (
            f"\n## Previous iteration's FAILING test output\n```\n{previous_failure[:2000]}\n```\n"
            "The implementation you produced last time FAILED against these tests. "
            "Fix what was wrong."
            if previous_failure
            else ""
        )
        # Reference implementation injection — adapts, never reinvents.
        reference_block = self._reference_prompt_block(alg)
        # Struct context — inject field definitions for shared types that
        # appear in the function's parameter types. Without this, the model
        # guesses field names on 40-field structs and gets them wrong.
        struct_context = self._struct_context_for(alg)
        signature = self._signature_for(alg)
        prompt = _IMPL_PROMPT.format(
            name=alg.name,
            category=alg.category,
            description=alg.description,
            math=alg.mathematical_description or "(none)",
            standards=", ".join(alg.referenced_standards) or "(none)",
            signature=signature,
            inputs=params,
            return_type=alg.return_type or "()",
            invariants="\n".join(
                f"- {inv.description}" for inv in alg.invariants
            ) or "(none)",
            test_vectors=tvecs,
            catalog_vectors=catalog_vec_text,
            reference_impls=reference_block,
            idiom_patterns=self._idiom_prompt_block(alg),
            struct_context=struct_context,
            error_context=self._error_context_for(alg),
            available_consts=self._consts_in_scope(module_source),
            current_body=current_body,
            previous_failure=prev_failure_section,
        )
        # Feed the ORIGINAL C source so the model TRANSLATES it faithfully (preserving
        # exact integer width/overflow/wraparound, sign handling, loop bounds, edge cases)
        # instead of re-inventing the algorithm from the spec. This is the single biggest
        # fill-quality lever for cold functions that compile-but-diverge.
        try:
            _src_root = getattr(self, "_source_root", None)
            if _src_root:
                from alchemist.implementer.reference_probe import (
                    collect_callee_context,
                    extract_c_function_body, extract_referenced_arrays,
                    extract_referenced_defines,
                )
                from alchemist.verifier.build_c_dll import discover_c_build as _disc
                _srcs, _incs = _disc(_src_root)
                for _cf in _srcs:
                    _cbody = extract_c_function_body(_cf, alg.name)
                    if _cbody:
                        # WALL 3 — control-flow structuring. Rust has no `goto`; a faithful
                        # translation of a C function that uses one needs an explicit recipe
                        # or the model emits `goto`/labels that don't compile. Give it the
                        # standard structured-equivalent transform; the differential still gates
                        # byte-exactness, so a wrong restructuring fails loudly.
                        _goto_section = ""
                        if re.search(r"\bgoto\b", _cbody):
                            _goto_section = (
                                "## This C function uses `goto`. Rust has NO goto — translate the "
                                "control flow into STRUCTURED safe Rust that is byte-exact "
                                "equivalent (same computation, same side effects, same result):\n"
                                "- A BACKWARD goto (to a label ABOVE it) is a LOOP: wrap that "
                                "region in `loop { … }`; the jump-back becomes `continue` (or the "
                                "loop's natural back-edge), and the loop-exit condition becomes a "
                                "`break`.\n"
                                "- A FORWARD goto (jumping DOWN, e.g. to a `cleanup:`/`done:` "
                                "label) is an early exit: use an early `return`, or `break "
                                "'label` out of a labeled block `'label: { … }`, running the "
                                "code at/after the label afterwards.\n"
                                "- Shared trailing code after a `done:` label (cleanup, a final "
                                "return value) must still run on EVERY path that jumped there.\n"
                                "- If the control flow is irreducible, use an explicit state "
                                "machine: `let mut state = …; loop { state = match state { … } }`.\n"
                                "Do NOT emit `goto`, labels-as-statements, or `unsafe`. Preserve "
                                "the exact arithmetic and evaluation order.\n\n"
                            )
                        # Feed the EXACT #define constants (start values, polynomials, magic
                        # numbers) the function references so the model uses them verbatim
                        # instead of guessing (e.g. CRC_START_64_WE = 0xFFFF..., not 0x0).
                        _defs = extract_referenced_defines(_cf, _cbody, include_dirs=_incs)
                        _def_section = ""
                        if _defs:
                            _def_section = (
                                "## Exact constants the function uses (from C `#define`s) — "
                                "use these VALUES verbatim; do NOT guess or truncate them:\n"
                                "```c\n" + "\n".join(_defs) + "\n```\n\n"
                            )
                        # Feed any lookup table(s) the function references so the model
                        # reproduces them EXACTLY instead of guessing (table-driven CRC/hash).
                        _tbls = extract_referenced_arrays(_cf, _cbody, include_dirs=_incs)
                        _tbl_section = _def_section
                        if _tbls:
                            _tbl_section = _def_section + (
                                "## Lookup table(s) the function reads are ALREADY defined in "
                                "your crate module as Rust `const` arrays with these EXACT names "
                                "and values. Reference them directly by name (e.g. "
                                "`TABLE[idx as usize]`); do NOT redefine or regenerate them:\n"
                                "```c\n" + "\n\n".join(_tbls) + "\n```\n\n"
                            )
                        # Feed the bodies of functions THIS one calls within the module
                        # (e.g. a lazy runtime-table initializer). A standalone updater
                        # like update_crc_16 shares crc_16's table; without seeing the
                        # init routine the model invents a DIFFERENT (wrong) table.
                        _callee_section = ""
                        try:
                            _callees = collect_callee_context(
                                _cbody, _srcs, include_dirs=_incs, exclude=(alg.name,))
                        except Exception:  # noqa: BLE001
                            _callees = []
                        if _callees:
                            _parts = []
                            for _cn, _cb, _cd in _callees:
                                _seg = ""
                                if _cd:
                                    _seg += "// exact constants: " + "; ".join(_cd) + "\n"
                                _parts.append(_seg + _cb)
                            _callee_section = (
                                "## Helper function(s) THIS function calls, defined elsewhere in "
                                "the same C module. It SHARES their state — most importantly a "
                                "lookup table filled by an init routine. Reproduce that shared "
                                "table/logic EXACTLY (same polynomial, shift DIRECTION, start "
                                "value); do NOT invent a different table for the standalone "
                                "function:\n```c\n" + "\n\n".join(_parts) + "\n```\n\n"
                            )
                        prompt = (
                            _tbl_section
                            + _callee_section
                            + _goto_section
                            + f"## Original C source for `{alg.name}` — translate this "
                            f"FAITHFULLY into safe Rust. Preserve the EXACT arithmetic, "
                            f"integer widths, sign "
                            f"handling, loop bounds and edge cases. IMPORTANT: C integer arithmetic wraps on overflow (2s-complement); use Rust wrapping_add/wrapping_mul/wrapping_sub for any arithmetic that could overflow so the result matches C EXACTLY (plain +,*,- panic on overflow in Rust and would diverge from C). Do NOT invent a "
                            f"different algorithm; match this C exactly.\n```c\n"
                            f"{_cbody}\n```\n\n" + prompt
                        )
                        break
        except Exception:  # noqa: BLE001
            pass
        resp = self.llm.call_structured(
            messages=[{"role": "user", "content": prompt}],
            tool_name="impl",
            tool_schema=schema,
            cached_context=self._cached_ctx,
            max_tokens=6000,
            temperature=temperature,
        )
        # Hard gate: if the LLM call failed (503, timeout, etc.), return None
        # so the caller SKIPS splicing. Without this, the error text was being
        # spliced as code, producing uncompilable Rust with ERROR: strings.
        if getattr(resp, "error", ""):
            return None
        if resp.structured and "content" in resp.structured:
            content = (resp.structured.get("content") or "").strip()
            # Some LLMs wrap their structured output in the schema itself:
            # `content` ends up being a JSON string describing the schema,
            # not the Rust code. Detect and drill in.
            content = _unwrap_llm_schema_leak(content)
            content = _normalize_filled_fn_name(content, alg.name)
            return content or None
        # Fallback: raw text
        raw = (resp.content or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:\w+)?\s*", "", raw)
            raw = re.sub(r"```\s*$", "", raw)
        raw = _unwrap_llm_schema_leak(raw)
        raw = _normalize_filled_fn_name(raw, alg.name)
        return raw or None

    def _multi_sample_attempt(
        self,
        alg: AlgorithmSpec,
        module_path: Path,
        original_source: str,
        current_body: str,
        *,
        previous_failure: str,
        crate_dir: Path,
        test_name_prefix: str | list[str],
    ):
        """Fan out multi_sample_n candidates, evaluate, pick best.

        Returns MultiSampleResult or None (when sampling can't make progress).
        """
        from alchemist.implementer.multi_sample import (
            make_cargo_evaluator,
            run_multi_sample,
        )

        _module_src = module_path.read_text(encoding="utf-8")

        def sampler(_idx: int) -> str | None:
            return self._prompt_for_impl(
                alg, current_body,
                previous_failure=previous_failure,
                temperature=self.multi_sample_temperature,
                module_source=_module_src,
            )

        def splicer(body: str) -> bool:
            body, _ = scrub_rust(body)
            body = self._strip_module_items(body)
            if scan_text("pending.rs", body):
                return False
            replaced = self._replace_fn_in_source(original_source, alg.name, body)
            if not replaced:
                return False
            module_path.write_text(replaced, encoding="utf-8")
            return True

        def reject_stub(body: str) -> bool:
            return bool(scan_text("pending.rs", body))

        evaluator = make_cargo_evaluator(crate_dir, test_name_prefix)
        try:
            return run_multi_sample(
                sampler=sampler,
                splicer=splicer,
                evaluator=evaluator,
                original_source=original_source,
                file_path=module_path,
                n_samples=self.multi_sample_n,
                reject_stub=reject_stub,
            )
        except Exception as e:  # noqa: BLE001
            console.print(f"  [dim]multi-sample skipped: {e}[/dim]")
            # Always restore original source on error
            module_path.write_text(original_source, encoding="utf-8")
            return None

    def _topo_sort_algorithms(self, algs: list[AlgorithmSpec]) -> list[AlgorithmSpec]:
        """Sort algorithms so dependencies come before dependents.

        Heuristics (OR'd):
          1. A's description mentions B's name as a function call.
          2. A's hardport source (if present) calls B. Authoritative when
             available — the hardport IS the correct impl, so any call it
             makes is a real runtime dependency.

        Functions with no dependencies go first, then their dependents.
        Unresolved cycles fall through to original order.
        """
        names = {a.name for a in algs}
        alg_by_name = {a.name: a for a in algs}

        # Pre-cache hardport bodies for fast lookup. Scanning the hardports
        # root for every function is cheap (dozens of files).
        from alchemist.references import registry as _reg
        hardport_text: dict[str, str] = {}
        hardports_root = _reg.REFERENCES_DIR
        for subject_hint in ("zlib",):
            base = hardports_root / f"{subject_hint}_hardports"
            if not base.exists():
                continue
            for path in base.rglob("*.rs"):
                try:
                    hardport_text[path.stem] = path.read_text(encoding="utf-8")
                except Exception:
                    continue

        def deps_of(a: AlgorithmSpec) -> set[str]:
            text = (a.description or "") + " " + (a.mathematical_description or "")
            hp = hardport_text.get(a.name, "")
            combined = text + "\n" + hp
            found: set[str] = set()
            for n in names:
                if n == a.name:
                    continue
                # Look for call-site patterns: `name(` or `name (`
                if re.search(rf"\b{re.escape(n)}\s*\(", combined):
                    found.add(n)
            return found

        # Compute in-degrees and do Kahn's algorithm
        deps = {a.name: deps_of(a) for a in algs}
        ordered: list[AlgorithmSpec] = []
        remaining = set(names)
        while remaining:
            # Find algs whose deps are all resolved
            ready = [n for n in remaining if not (deps[n] & remaining)]
            if not ready:
                # Cycle — just append remaining in original order
                ordered.extend(a for a in algs if a.name in remaining)
                break
            # Stable order: sort by original index
            ready.sort(key=lambda n: next(i for i, a in enumerate(algs) if a.name == n))
            for n in ready:
                ordered.append(alg_by_name[n])
                remaining.discard(n)
        return ordered

    def _struct_context_for(self, alg: AlgorithmSpec) -> str:
        """Build a struct-field context block for types referenced in params.

        When a function takes `&mut DeflateState`, the model needs to see
        the exact field names and types to generate compiling code. We scan
        the workspace's types module file for struct definitions that match
        any type name appearing in the function's parameters.

        Follows type references transitively: if DeflateStream has a field
        `state: DeflateState`, both structs are included. Depth-limited to
        avoid runaway inclusion of every shared type.
        """
        _STDLIB_GENERIC_NAMES = {
            "Vec", "Option", "Result", "Box", "String", "HashMap",
            "Arc", "Mutex", "Rc", "RefCell", "Cow", "Rc", "Cell",
            "BTreeMap", "BTreeSet", "HashSet", "VecDeque",
        }

        def _collect_type_names(type_str: str) -> set[str]:
            names: set[str] = set()
            for m in re.finditer(r"\b([A-Z]\w+)\b", type_str or ""):
                name = m.group(1)
                if name not in _STDLIB_GENERIC_NAMES:
                    names.add(name)
            return names

        # Collect type names from parameter types
        type_names_wanted: set[str] = set()
        for p in alg.inputs or []:
            type_names_wanted |= _collect_type_names(p.rust_type)

        if not type_names_wanted:
            return "(no shared types referenced by this function's parameters)"

        # Find the types module file in the workspace
        if not hasattr(self, '_workspace_dir'):
            return "(struct context unavailable — no workspace dir)"

        types_files: list[Path] = []
        for rs in Path(self._workspace_dir).rglob("types.rs"):
            if "target" not in str(rs):
                types_files.append(rs)

        if not types_files:
            return "(no types.rs found in workspace)"

        # Walk the type-reference graph, collecting all referenced structs.
        # Depth-limited so we don't include every shared type in the workspace.
        MAX_DEPTH = 3
        all_text = "\n".join(
            tf.read_text(encoding="utf-8", errors="replace") for tf in types_files
        )
        found_defs: dict[str, str] = {}
        to_visit: list[tuple[str, int]] = [(n, 0) for n in type_names_wanted]
        while to_visit:
            name, depth = to_visit.pop()
            if name in found_defs or depth > MAX_DEPTH:
                continue
            pattern = re.compile(
                rf"((?:#\[[^\]]*\]\s*\n)*"
                rf"pub\s+(?:struct|enum|type)\s+{re.escape(name)}\b[^{{;]*"
                rf"(?:\{{[^}}]*\}}|;))",
                re.MULTILINE | re.DOTALL,
            )
            m = pattern.search(all_text)
            if not m:
                continue
            defn = m.group(0).strip()
            if len(defn) > 2000:
                defn = defn[:2000] + "\n    // ... (truncated)"
            found_defs[name] = defn
            # Recurse into types referenced inside this struct's body.
            for sub in _collect_type_names(defn):
                if sub not in found_defs:
                    to_visit.append((sub, depth + 1))

        if not found_defs:
            return "(referenced types not found in workspace types.rs)"
        # Stable order — primary type first, then alphabetical.
        primary = sorted(type_names_wanted & found_defs.keys())
        rest = sorted(k for k in found_defs if k not in type_names_wanted)
        blocks = [f"```rust\n{found_defs[n]}\n```" for n in primary + rest]

        return (
            "The following types are used in this function's parameters. "
            "Use EXACTLY these field names and types:\n\n"
            + "\n\n".join(blocks)
        )

    def _idiom_prompt_block(self, alg: AlgorithmSpec) -> str:
        """Surface C->safe-Rust idiom patterns relevant to this function.

        Matches the function's C source against the idiom catalog (WS6) and
        injects only the patterns whose C-signals fire, so the model gets the
        known safe-Rust model for constructs it's about to hit (advancing
        pointers, goto state machines, unions, aliasing, shift overflow, ...).
        Cheap and additive: a false-positive hint costs little; a missed idiom
        is a class of bug (see docs/PATH_TO_AUTONOMY.md, WS6).
        """
        src_root = getattr(self, "_source_root", None)
        if src_root is None:
            return ""
        try:
            from alchemist.catalog import match_idioms, render_prompt_hints
            from alchemist.implementer.reference_probe import _find_body_in_sources
        except Exception:
            return ""
        c_body = None
        try:
            c_body = _find_body_in_sources(alg, src_root)
        except Exception:
            c_body = None
        if not c_body:
            return ""
        hits = match_idioms(c_body)
        if not hits:
            return ""
        # Cap to the most load-bearing few to avoid prompt bloat on macro-heavy fns.
        block = render_prompt_hints(hits[:6])
        return "\n" + block if block else ""

    def _reference_prompt_block(self, alg: AlgorithmSpec) -> str:
        """Pull any matching reference implementations from the library.

        Tries two lookup paths:
          1. Direct — by algorithm name (alias-tolerant).
          2. By cited standards — e.g. spec says "RFC 1950" → Adler-32 ref.
        """
        from alchemist.references import find_references
        from alchemist.references.registry import references_for_standards

        candidates = []
        # Ephemeral probe refs take priority — they were synthesized for
        # THIS specific function from THIS specific C source, so they're
        # more precise than any category-level curated match.
        probe_ref = getattr(self, "_probe_refs", {}).get(alg.name)
        if probe_ref is not None:
            candidates.append(probe_ref)
        # Try direct name match (alias-tolerant)
        direct = find_references(alg.name)
        if direct.ok:
            candidates.extend(direct.impls)
        # Try by cited standards
        if alg.referenced_standards:
            candidates.extend(references_for_standards(alg.referenced_standards))
        # Try by category-qualified name (e.g. "adler32" from "adler32_z")
        base_name = alg.name.rstrip("_").rsplit("_", 1)[0] if "_" in alg.name else alg.name
        if base_name != alg.name:
            fallback = find_references(base_name)
            if fallback.ok:
                candidates.extend(fallback.impls)

        # Dedup keeping order
        seen: set[tuple[str, str]] = set()
        unique: list = []
        for impl in candidates:
            key = (impl.algorithm, impl.variant)
            if key not in seen:
                seen.add(key)
                unique.append(impl)

        if not unique:
            return ""
        # Limit to at most 2 variants (avoid prompt explosion on multi-variant entries)
        snippets = [impl.as_prompt_snippet() for impl in unique[:2]]
        header = (
            "\n## Reference implementation(s) — adapt to the signature above\n"
            "The following Rust is a known-good implementation of this exact algorithm. "
            "Use it as the template; change ONLY names and the signature/return type to match "
            "the spec above (e.g. if the spec returns `Vec<u8>`, return `the_array.to_vec()`).\n\n"
            "CRITICAL — CONSTANTS: KEEP any constants/lookup tables the reference declares "
            "(its IV, round constants K, S-boxes, etc.) UNLESS an identically-named constant is "
            "already listed as in scope below — declare them yourself so the function compiles. "
            "Do NOT assume anything is imported. It is fine to include the `const`/`static` "
            "declarations the reference shows; just return a working, self-contained function "
            "(plus its constants) and no unrelated module items.\n"
        )
        return header + "\n\n".join(snippets)

    def _signature_for(self, alg: AlgorithmSpec) -> str:
        params: list[str] = [
            f"{_sanitize_param_name(p.name, k)}: {p.rust_type}"
            for k, p in enumerate(alg.inputs)]
        ret = alg.return_type or "()"
        if ret in ("", "()"):
            return f"pub fn {alg.name}({', '.join(params)})"
        return f"pub fn {alg.name}({', '.join(params)}) -> {ret}"

    # --- Module-item stripping ---

    @staticmethod
    def _strip_module_items(code: str) -> str:
        """Remove module-level items (use/static/const) that the LLM emits
        above the function definition.

        The LLM sometimes prefixes its response with lines like
        ``use crate::foo;`` or ``static X: u32 = ...;``.  These leak into
        the file even after a revert because ``_replace_fn_in_source`` only
        replaces from the function signature onwards.

        This helper strips such lines that appear *before* the first
        ``pub fn`` / ``fn`` line.  ``const fn`` is kept (it is a function
        qualifier, not a module-level const binding).
        """
        lines = code.splitlines(keepends=True)
        first_fn_idx: int | None = None
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            # Match "pub fn", "pub(crate) fn", "fn", "pub const fn", etc.
            if re.match(r"(?:pub\s*(?:\([^)]*\)\s*)?)?(?:async\s+|unsafe\s+|const\s+)*fn\s", stripped):
                first_fn_idx = idx
                break

        if first_fn_idx is None:
            # No function found — return as-is (caller will reject anyway)
            return code

        kept: list[str] = []
        for idx, line in enumerate(lines):
            if idx < first_fn_idx:
                stripped = line.lstrip()
                # Drop lines that are module-level items
                if re.match(r"use\s", stripped):
                    continue
                if re.match(r"static\s", stripped):
                    continue
                # "const " but NOT "const fn"
                if re.match(r"const\s", stripped) and not re.match(r"const\s+fn\s", stripped):
                    continue
            kept.append(line)
        return "".join(kept)

    # --- Source splicing ---

    _FN_BLOCK_RE = re.compile(
        r"(?P<attrs>(?:#\[[^\]]*\]\s*)*)"
        r"(?P<doc>(?:///[^\n]*\n)*)"
        r"(?P<sig>(?:pub\s+(?:\([^\)]*\)\s*)?)?"
        r"(?:async\s+|const\s+|unsafe\s+)*"
        r"fn\s+{name}\s*(?:<[^>]*>)?\s*\([^)]*\)[^{{;]*)"
        r"\{"
    )

    def _extract_fn_body(self, text: str, name: str) -> str | None:
        m = self._find_fn(text, name)
        if not m:
            return None
        start = m["body_start"]
        end = m["body_end"]
        return text[start:end]

    def _stub_refused_fn(self, alg, module, crate_spec, workspace_dir) -> bool:
        """Reset a REFUSED function to a compiling `unimplemented!()` stub so its last
        (broken/non-compiling) body cannot poison the crate and block EVERY verified
        sibling's verification. This is the crate-level "verified core + honest refusal
        tail": a function the model couldn't translate becomes an honest stub, and the
        functions it CAN translate still compile and verify. The signature is preserved
        exactly (only the body becomes the stub). Returns True if a reset was applied."""
        module_path = workspace_dir / crate_spec.name / "src" / f"{module.name}.rs"
        if not module_path.exists():
            return False
        src = module_path.read_text(encoding="utf-8")
        sig_m = re.search(
            r"((?:pub\s+)?fn\s+" + re.escape(alg.name) + r"\s*(?:<[^>]*>)?\s*\([^{]*?)\{",
            src, re.DOTALL)
        if not sig_m:
            return False
        stub_fn = sig_m.group(1).rstrip() + (
            f' {{\n    unimplemented!("refused: {alg.name} — no verified translation")\n}}')
        replaced = self._replace_fn_in_source(src, alg.name, stub_fn)
        if replaced is None or replaced == src:
            return False
        module_path.write_text(replaced, encoding="utf-8")
        return True

    def _replace_fn_in_source(self, text: str, name: str, new_fn_text: str) -> str | None:
        m = self._find_fn(text, name)
        if not m:
            return None
        # Protection against body-only replacements (legacy cache format).
        # `new_fn_text` MUST be a full fn item: either starts with attrs/docs,
        # has `pub fn NAME`, `fn NAME`, or similar. If it's body-only, the
        # splice corrupts the module (observed: cache hit for crc32_combine_op
        # stored just the body, splice produced a naked body in place of the
        # fn declaration, crate lost 14+ functions in the blast radius).
        stripped = new_fn_text.strip()
        looks_like_body_only = (
            not re.search(r"\bfn\s+" + re.escape(name) + r"\b", stripped)
            and not stripped.startswith(("pub ", "#[", "///", "//!"))
        )
        if looks_like_body_only:
            return None
        # Replace the entire fn item (attrs + signature + body)
        replaced = text[:m["item_start"]] + stripped + "\n" + text[m["item_end"]:]
        # Integrity guard: LLM sometimes returns whole-file contents that
        # corrupt the module when spliced (recently observed: lib.rs loses
        # all `pub mod X;` declarations, modules lose the skeleton header).
        # Guard in two tiers:
        #   1. If the text carried required boilerplate (skeleton markers,
        #      use statements, pub mod items) — the splice MUST preserve it.
        #      Erasing a marker is a clear corruption signal.
        #   2. Length guard only applies when the original was substantially
        #      populated (>=500 chars). Below that, small test modules and
        #      freshly-scaffolded stubs are legitimately small.
        required_markers = ("#![allow(unused", "use crate::")
        for marker in required_markers:
            if marker in text and marker not in replaced:
                return None
        if len(text) >= 500 and len(replaced) < max(120, len(text) // 3):
            return None
        return replaced

    def _find_fn(self, text: str, name: str) -> dict | None:
        # Skeleton renames fns via _snake (e.g., `zlibCompileFlags` →
        # `zlib_compile_flags`). Spec's alg.name may be the original
        # camelCase. Try both forms when searching the source.
        from alchemist.implementer.skeleton import _snake
        candidates = list({name, _snake(name)})
        m = None
        for cand in candidates:
            pat = re.compile(
                self._FN_BLOCK_RE.pattern.replace("{name}", re.escape(cand)),
                re.MULTILINE,
            )
            m = pat.search(text)
            if m:
                break
        if not m:
            return None
        sig_end = m.end()  # position just past the `{` matched by _FN_BLOCK_RE
        # _FN_BLOCK_RE's last token is `{`, so sig_end - 1 is the `{`.
        # Use string/comment-aware brace matching via the shared helper
        # (Phase 0 Bug #4: naive counter miscounted braces inside strings).
        from alchemist.implementer.scrubber import find_matching_brace
        open_brace = sig_end - 1
        body_end = find_matching_brace(text, open_brace)
        if body_end < 0:
            return None
        # Include trailing newline if present
        item_end = body_end + 1
        if item_end < len(text) and text[item_end] == "\n":
            item_end += 1
        return dict(
            item_start=m.start(),
            body_start=sig_end,
            body_end=body_end,
            item_end=item_end,
        )

    # --- Refusal-time escalation: verifier-policed structural decomposition ---

    def _attempt_structural_decomposition(
        self,
        alg: AlgorithmSpec,
        module: ModuleSpec,
        crate_spec: CrateSpec,
        module_path: Path,
        crate_dir: Path,
        workspace_dir: Path,
        test_name_prefix: str,
    ) -> bool:
        """Break a refused function into gcc-proven byte-exact helpers, then
        translate the easier decomposed unit (see implementer/structural_decomp).

        Only fires for the ONE differential shape the offline equivalence gate
        can fuzz today (buf_transform: `int f(char*in,int,char*out,int)`). Sound
        by construction: an unproven split is discarded, and a failed or
        unverified translation reverts the module — so this can only turn a
        refusal into a
        verified win, never degrade a passing function. Returns True only on a
        2x-verified differential pass.
        """
        src_root = getattr(self, "_source_root", None)
        if src_root is None:
            return False
        src_root = Path(src_root)

        # (1) Locate the original C function + a preamble carrying its file's
        #     globals/#includes/sibling prototypes.
        loc = self._c_function_and_preamble(alg, src_root)
        if loc is None:
            return False
        fn_text, preamble, include_dirs = loc

        # (2) Shape gate — the offline equivalence fuzzer only supports
        #     buf_transform today. Classify from the C prototype.
        from alchemist.implementer.structural_decomp import (
            _classify_shape,
            propose_and_verify_decomposition,
        )
        proto = fn_text.split("{", 1)[0].strip()
        if _classify_shape(proto) != "buf_transform":
            return False

        # (3) Model callback for the (untrusted) split proposal.
        def _call_llm(prompt: str, step: str) -> "str | None":
            try:
                resp = self.llm.call_structured(
                    messages=[{"role": "user", "content": prompt}],
                    tool_name="decompose",
                    tool_schema={
                        "type": "object",
                        "properties": {"content": {"type": "string"}},
                        "required": ["content"],
                    },
                    cached_context=getattr(self, "_cached_ctx", None),
                    max_tokens=4000,
                    temperature=0.0 if getattr(self, "_deterministic", False) else 0.2,
                )
            except Exception:  # noqa: BLE001
                return None
            if getattr(resp, "error", ""):
                return None
            if resp.structured and "content" in resp.structured:
                return resp.structured.get("content")
            return getattr(resp, "content", None)

        console.print(
            f"  [cyan]{alg.name}: refused — attempting verifier-policed "
            f"structural decomposition[/cyan]"
        )
        deco = propose_and_verify_decomposition(
            fn_source=fn_text,
            fn_name=alg.name,
            shape="buf_transform",
            original_c=fn_text,
            call_llm=_call_llm,
            include_dirs=include_dirs,
            preamble=preamble,
        )
        if deco is None or not deco.verified_equivalent:
            console.print(
                f"  [yellow]{alg.name}: no proven-equivalent split — "
                f"keeping refusal[/yellow]"
            )
            return False
        console.print(
            f"  [green]{alg.name}: proven-equivalent C split "
            f"({len(deco.helpers)} helper(s)); {deco.equivalence_report}[/green]"
        )

        # (4) Translate the PROVEN decomposed C unit → Rust, splice, re-verify
        #     with the SAME differential test. The driver keeps the public
        #     signature (its differential test is unchanged); helpers are
        #     private and verified transitively through the driver's byte-exact
        #     output.
        rust_blob = self._translate_decomposition_to_rust(alg, deco, module_path)
        if not rust_blob:
            return False
        current = module_path.read_text(encoding="utf-8")
        replaced = self._replace_fn_in_source(current, alg.name, rust_blob)
        if replaced is None:
            return False
        module_path.write_text(replaced, encoding="utf-8")
        ok_compile, _ = _run_cargo_check(crate_dir, timeout=180)
        if not ok_compile:
            module_path.write_text(current, encoding="utf-8")
            return False
        ok_twice, total = self._verify_cached_win_twice(crate_dir, test_name_prefix)
        if not (ok_twice and total > 0):
            module_path.write_text(current, encoding="utf-8")
            return False
        console.print(
            f"  [green]{alg.name}: DECOMPOSITION WIN — byte-exact via "
            f"{len(deco.helpers)}-helper split (2x, {total} tests)[/green]"
        )
        return True

    def _c_function_and_preamble(
        self, alg: AlgorithmSpec, src_root: Path,
    ) -> "tuple[str, str, list[Path]] | None":
        """Return (full C fn text, preamble, include_dirs) for the equivalence
        gate. The preamble is the containing .c file with the target function
        removed, so every global/#include/sibling prototype the split needs is
        present when gcc compiles both the original and the decomposed unit."""
        from alchemist.implementer.reference_probe import extract_c_function_body

        candidate_paths: list[Path] = []
        for sf in alg.source_files or []:
            p = Path(sf)
            candidate_paths.append(p if p.is_absolute() else src_root / sf)
        if not candidate_paths:
            candidate_paths = list(src_root.rglob("*.c"))

        try:
            from alchemist.verifier.build_c_dll import discover_c_build
            _srcs, inc = discover_c_build(src_root)
            base_inc = list(inc) if inc else [src_root]
        except Exception:  # noqa: BLE001
            base_inc = [src_root]

        for fn_name in (alg.source_functions or [alg.name]):
            for path in candidate_paths:
                if not path.exists():
                    continue
                fn_text = extract_c_function_body(path, fn_name)
                if not fn_text:
                    continue
                try:
                    file_text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # Normalize newlines: tree-sitter reads raw bytes (may keep
                # CRLF on Windows) while read_text applies universal-newline
                # translation, so a raw substring/replace can miss. gcc is fine
                # with LF, so canonicalize both to LF before splicing.
                fn_norm = fn_text.replace("\r\n", "\n").replace("\r", "\n")
                file_norm = file_text.replace("\r\n", "\n").replace("\r", "\n")
                if fn_norm not in file_norm:
                    continue
                preamble = file_norm.replace(fn_norm, "", 1)
                include_dirs = list(base_inc)
                if path.parent not in include_dirs:
                    include_dirs = [path.parent] + include_dirs
                return fn_norm, preamble, include_dirs
        return None

    def _translate_decomposition_to_rust(
        self, alg: AlgorithmSpec, deco, module_path: Path,
    ) -> "str | None":
        """Prompt the model to translate a proven decomposed C unit (helpers +
        driver) into one Rust blob: private helper fns followed by the public
        driver fn. Anti-stub gated; must contain the driver fn or it's rejected."""
        module_source = self._strip_test_module(
            module_path.read_text(encoding="utf-8"))
        helpers_c = "\n\n".join(h.source for h in deco.helpers)
        prompt = (
            "Translate the following C into safe Rust. The function was split "
            "into small helpers plus a driver; the split is PROVEN byte-exact "
            "against the original C, so translate it faithfully piece by piece.\n\n"
            "Requirements:\n"
            f"- Emit the driver as `pub fn {alg.name}(...)` with EXACTLY the "
            f"signature it already has in the module shown below.\n"
            "- Emit each helper as a PRIVATE `fn` (no `pub`). Keep helper names.\n"
            "- The driver must call the helpers, mirroring the C control flow.\n"
            "- C integer arithmetic wraps (2s-complement): use wrapping_add / "
            "wrapping_mul / wrapping_sub for any arithmetic that could overflow "
            "so results match C EXACTLY (plain +,*,- panic on overflow in Rust).\n"
            "- Return ONLY Rust source: the helper fns followed by the driver "
            "fn. No module-level use/const/static/mod items, no prose.\n\n"
            f"## Existing module (for the driver's exact signature + types)\n"
            f"```rust\n{module_source[:4000]}\n```\n\n"
            f"## Helper C functions\n```c\n{helpers_c}\n```\n\n"
            f"## Driver C ({alg.name})\n```c\n{deco.driver_source}\n```\n"
        )
        try:
            resp = self.llm.call_structured(
                messages=[{"role": "user", "content": prompt}],
                tool_name="impl",
                tool_schema={
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                },
                cached_context=getattr(self, "_cached_ctx", None),
                max_tokens=6000,
                temperature=0.0 if getattr(self, "_deterministic", False) else 0.15,
            )
        except Exception:  # noqa: BLE001
            return None
        if getattr(resp, "error", ""):
            return None
        if resp.structured and "content" in resp.structured:
            content = (resp.structured.get("content") or "").strip()
        else:
            content = (getattr(resp, "content", "") or "").strip()
        if not content:
            return None
        content, _ = scrub_rust(content)
        content = self._strip_module_items(content)
        # Anti-stub: a decomposition win must be real code, never a placeholder.
        if scan_text("pending.rs", content):
            return None
        # Must contain the driver fn (either the raw or snake-cased name).
        from alchemist.implementer.skeleton import _snake
        names = {alg.name, _snake(alg.name)}
        if not any(re.search(r"\bfn\s+" + re.escape(n) + r"\b", content) for n in names):
            return None
        return content

    def _holistic_fix(self, crate_dir: Path, alg: AlgorithmSpec, error_ctx: str) -> None:
        """Escalation tier: whole-crate fix via the holistic fixer."""
        from alchemist.implementer.holistic import HolisticFixer
        console.print(f"  [magenta]{alg.name}: holistic escalation[/magenta]")
        spec_ctx = (
            f"Algorithm: {alg.name}\n"
            f"Category: {alg.category}\n"
            f"Description: {alg.description}\n"
            f"Standards: {', '.join(alg.referenced_standards) or '(none)'}"
        )
        # Let holistic iterate (fix error A, then the error B it exposes), but
        # rely on its own no-progress guard (P0.5) to bail after 2 consecutive
        # no-op/empty patches instead of grinding — so a productive multi-step
        # fix isn't cut off at one pass, and a stuck model still can't waste the
        # budget silently.
        fixer = HolisticFixer(llm=self.llm, max_iter=3, reject_stubs=True)
        hr = fixer.fix_crate(crate_dir, spec_context=spec_ctx, extra_error_ctx=error_ctx)
        if hr.bail_reason:
            console.print(f"  [yellow]{hr.bail_reason}[/yellow]")

    def _fix_missing(
        self,
        api: ApiCompletenessReport,
        specs: list[ModuleSpec],
        arch: CrateArchitecture,
        workspace_dir: Path,
    ) -> None:
        """Re-prompt for each missing function in isolation."""
        for miss in api.missing:
            crate_dir = workspace_dir / miss.crate
            # Locate the spec for this algorithm
            spec_module = next((m for m in specs if m.name == miss.module), None)
            if not spec_module:
                continue
            alg = next((a for a in spec_module.algorithms if a.name == miss.algorithm), None)
            if not alg:
                continue
            # Append a pub fn stub at the bottom of the module and try filling it
            module_path = crate_dir / "src" / f"{miss.module}.rs"
            if not module_path.exists():
                continue
            existing = module_path.read_text(encoding="utf-8")
            if f"pub fn {miss.c_function}" in existing:
                continue
            # Append a temporary stub purely so the splicer has a target to
            # replace. CRITICAL: after _fill_in_function runs, the stub must
            # either be replaced with real code OR be reverted. A surviving
            # stub in the output violates P1 (no placeholder bodies).
            sig = f"pub fn {miss.c_function}(input: &[u8]) -> u32"
            stub = (
                f"\n\n/// Auto-added stub to satisfy API completeness check.\n"
                f"/// Re-prompt will fill this in.\n"
                f"{sig} {{\n"
                f"    let _ = input;\n"
                f"    unimplemented!(\"missing fn: {miss.c_function}\")\n"
                f"}}\n"
            )
            module_path.write_text(existing + stub, encoding="utf-8")
            synthetic = AlgorithmSpec(
                name=miss.c_function,
                display_name=miss.c_function,
                category=alg.category,
                description=alg.description,
                inputs=alg.inputs,
                return_type=alg.return_type,
                referenced_standards=alg.referenced_standards,
                test_vectors=alg.test_vectors,
                mathematical_description=alg.mathematical_description,
            )
            fill_attempt = self._fill_in_function(
                synthetic, spec_module,
                next((c for c in arch.crates if c.name == miss.crate), None) or arch.crates[0],
                specs, arch, workspace_dir,
            )
            # If the fill failed, the stub is still in the file. Revert it
            # rather than leave an unimplemented!() body in the output.
            #
            # Prior bug: exact-string match on the stub message missed
            # - LLM rewording to `todo!("fixme")` or similar
            # - Whitespace changes from rustfmt
            # - Multi-statement bodies wrapping the stub
            # has_stub_for_fn handles all three via regex + canonical match.
            if not fill_attempt.tests_passed:
                after = module_path.read_text(encoding="utf-8")
                from alchemist.implementer.anti_stub import has_stub_for_fn
                if has_stub_for_fn(after, miss.c_function):
                    # Stub survived — strip it and restore prior content
                    module_path.write_text(existing, encoding="utf-8")
                    console.print(
                        f"  [red]{miss.c_function}: fill failed, stub "
                        f"removed from output (P1: no placeholder bodies)[/red]"
                    )

    def _ensure_probe_ref(self, alg: AlgorithmSpec) -> bool:
        """Lazily synthesize a reference impl for this algorithm if needed.

        Called per-function during Phase C when iter-1 fails. Skipped if:
          - a curated disk reference exists (via find_references)
          - a probe has already been attempted for this algorithm this run

        Returns True iff a new probe ref was registered (so the caller can
        re-prompt with the fresh reference on iter 2+).
        """
        if alg.name in self._probe_attempted:
            return False
        self._probe_attempted.add(alg.name)
        from alchemist.implementer.reference_probe import (
            probe_algorithm, probe_result_as_reference,
        )
        from alchemist.references.registry import find_references
        if find_references(alg.name).ok:
            return False
        if self._source_root is None:
            return False
        sig = self._signature_for(alg)
        probe = probe_algorithm(
            alg,
            source_root=self._source_root,
            llm=self.llm,
            signature=sig,
            struct_context=self._struct_context_for(alg),
            cached_context=self._cached_ctx,
        )
        ref = probe_result_as_reference(probe, sig)
        if ref is None:
            return False
        self._probe_refs[alg.name] = ref
        console.print(f"    [cyan]{alg.name}: probe-synthesized ref injected[/cyan]")
        return True

    def _backfill_fuzz_vectors(
        self,
        specs: list[ModuleSpec],
        specs_dir: Path | None = None,
    ) -> None:
        """For every algorithm without authored test_vectors, fuzz-generate.

        Uses the C reference DLL / shims (when discoverable) to compute
        ground-truth outputs. Vectors are set in-place so Phase B emits real
        correctness tests.

        Provenance + persistence: every generated vector is tagged with an
        oracle fingerprint in its `source` field. Tagged vectors are ALWAYS
        regenerated on the next run — a persisted vector must never outlive
        a fix to its oracle (the crc_word_big lesson) — while untagged
        (extractor- or hand-authored) vectors are never touched. When
        `specs_dir` is given, modules whose vectors changed are written back
        to their spec checkpoint so the vectors become durable artifacts.
        """
        from alchemist.standards import lookup_test_vectors
        # Look up the C DLL for this translation. Convention: subjects
        # directory contains a reference DLL the extractor can see.
        # For zlib we use verify/zlib1.dll.
        dll_path = self._locate_c_dll()
        if dll_path is None or not dll_path.exists():
            return
        try:
            from alchemist.extractor.fuzz_vectors import (
                load_zlib_dll, ZLIB_BINDINGS, ZLIB_PURE_REFERENCES, fuzz_for_spec,
                ZLIB_BYTE_TRANSFORMS, fuzz_byte_transform,
            )
            from alchemist.extractor.state_mutator import (
                ZLIB_STATE_MUTATORS, fuzz_state_mutator,
            )
            from alchemist.extractor.c_shim_fuzz import (
                ZLIB_SHIM_BINDINGS, ZLIB_SHIM_PURE_BINDINGS,
                ZLIB_SHIM_OBSERVER_BINDINGS, ZLIB_INFLATE_SHIM_BINDINGS,
                locate_zlib_shim, locate_zlib_inflate_shim, _load_shim,
                fuzz_with_shim, fuzz_pure_shim, fuzz_observer_shim,
                TREE_BUILDER_FUZZERS, INFLATE_FUZZERS,
            )
            dll = load_zlib_dll(dll_path)
            # Load the C shim DLL if present — its C-reference-based
            # state-mutator vectors take priority over Python reference ports.
            shim_path = locate_zlib_shim()
            shim_dll = _load_shim(shim_path) if shim_path else None
            # Companion inflate-side shim (separate DLL due to header
            # include-guard conflicts between deflate.h and inflate.h).
            inflate_shim_path = locate_zlib_inflate_shim()
            inflate_shim_dll = (
                _load_shim(inflate_shim_path) if inflate_shim_path else None
            )
        except Exception as e:  # noqa: BLE001
            console.print(f"  [dim]fuzz backfill skipped: {e}[/dim]")
            return
        # Checksum shim (crc_word / crc_word_big / multmodp / x2nmodp — the
        # statics zlib1.dll doesn't export). Optional: older checkouts don't
        # have it. Oracle integrity: the shim must agree with the pure-Python
        # cross-check references before it is allowed to mint vectors; a
        # disagreement between oracles is a stop-the-line event, not a choice.
        from alchemist.extractor.oracle_tags import (
            OracleDisputeError,
            is_tagged,
            oracle_tag_for_callable,
            oracle_tag_for_file,
            tag_vectors,
        )

        checksum_shim_dll = None
        checksum_shim_path = None
        try:
            from alchemist.extractor.c_shim_fuzz import (
                ZLIB_CHECKSUM_SHIM_PURE_BINDINGS,
                crosscheck_checksum_shim,
                locate_zlib_checksum_shim,
            )
            checksum_shim_path = locate_zlib_checksum_shim()
            if checksum_shim_path:
                candidate = _load_shim(checksum_shim_path)
                mismatches = crosscheck_checksum_shim(candidate)
                if mismatches:
                    raise OracleDisputeError(
                        "checksum shim disagrees with pure-Python cross-check "
                        f"references ({len(mismatches)} mismatches, first: "
                        f"{mismatches[0]}) — REFUSING to generate vectors from "
                        "a disputed oracle"
                    )
                checksum_shim_dll = candidate
        except ImportError:
            ZLIB_CHECKSUM_SHIM_PURE_BINDINGS = {}

        # Non-zlib subjects: the oracle is the subject's own compiled C
        # (built by _locate_c_dll) and the bindings derive from its headers.
        # The zlib shim/pure-reference registries are zlib-shaped and must
        # not leak — a name collision would fuzz the wrong ABI.
        src_root = getattr(self, "_source_root", None)
        generic_subject = (
            src_root is not None and "zlib" not in Path(src_root).name.lower()
        )
        subject_sigs: dict = {}
        if generic_subject:
            from alchemist.verifier.auto_config import (
                collect_subject_signatures,
                make_checksum_bindings,
            )
            all_algs = [a for m in specs for a in (m.algorithms or [])]
            _sigs = collect_subject_signatures(Path(src_root))
            subject_sigs = {s.name: s for s in _sigs}
            subject_bindings = make_checksum_bindings(_sigs, all_algs)
            subject_pure_refs: dict = {}
            shim_dll = None
            inflate_shim_dll = None
            checksum_shim_dll = None
        else:
            subject_bindings = ZLIB_BINDINGS
            subject_pure_refs = ZLIB_PURE_REFERENCES

        added = 0
        touched_modules: set[str] = set()
        # Tagged vectors we cleared for regeneration, keyed by identity of
        # the algorithm object. If no oracle produced replacements (e.g. the
        # shim DLL that minted them isn't built on this machine), the
        # originals are RESTORED with a loud warning — zero vectors would
        # silently reopen the compile-only-pass loophole and, with
        # persistence, durably delete them from the checkpoint.
        cleared_for_regen: dict[int, tuple] = {}

        def _accept(mod, alg, vectors, tag: str) -> None:
            nonlocal added
            if vectors:
                alg.test_vectors = tag_vectors(vectors, tag)
                added += len(vectors)
                touched_modules.add(mod.name)

        for mod in specs:
            for alg in mod.algorithms:
                if alg.test_vectors:
                    if all(is_tagged(v) for v in alg.test_vectors):
                        # Machine-generated with recorded provenance —
                        # regenerate rather than trust: a stale persisted
                        # vector must never shadow a fixed oracle.
                        cleared_for_regen[id(alg)] = (mod, alg, alg.test_vectors)
                        alg.test_vectors = []
                    else:
                        continue  # authored vectors — never clobber
                # C-shim pure-function path (checksum statics)
                if (checksum_shim_dll is not None
                        and alg.name in ZLIB_CHECKSUM_SHIM_PURE_BINDINGS):
                    vectors = fuzz_pure_shim(
                        checksum_shim_dll, alg,
                        ZLIB_CHECKSUM_SHIM_PURE_BINDINGS[alg.name],
                    )
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", checksum_shim_path))
                    if vectors:
                        continue
                # C-shim pure-function path
                if shim_dll is not None and alg.name in ZLIB_SHIM_PURE_BINDINGS:
                    vectors = fuzz_pure_shim(
                        shim_dll, alg, ZLIB_SHIM_PURE_BINDINGS[alg.name],
                    )
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", shim_path))
                    continue
                # Huffman tree-builder path — dedicated fuzzers for fns that
                # take a `tree: &[TreeElement]` slice alongside the state
                # (doesn't fit the scalar extra-arg model).
                if shim_dll is not None and alg.name in TREE_BUILDER_FUZZERS:
                    vectors = TREE_BUILDER_FUZZERS[alg.name](shim_dll, alg)
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", shim_path))
                    continue
                # C-shim state-mutator path (deflate DLL)
                if shim_dll is not None and alg.name in ZLIB_SHIM_BINDINGS:
                    vectors = fuzz_with_shim(
                        shim_dll, alg, ZLIB_SHIM_BINDINGS[alg.name],
                    )
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", shim_path))
                    continue
                # Dedicated inflate fuzzers that also need the deflate shim to
                # synthesize valid Huffman inputs (inflate_table).
                if (
                    inflate_shim_dll is not None
                    and shim_dll is not None
                    and alg.name in INFLATE_FUZZERS
                ):
                    vectors = INFLATE_FUZZERS[alg.name](
                        inflate_shim_dll, shim_dll, alg)
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", inflate_shim_path))
                    continue
                # C-shim state-mutator path (inflate DLL) — separate DLL
                # because inflate.h / deflate.h can't share a CU.
                if (
                    inflate_shim_dll is not None
                    and alg.name in ZLIB_INFLATE_SHIM_BINDINGS
                ):
                    vectors = fuzz_with_shim(
                        inflate_shim_dll, alg,
                        ZLIB_INFLATE_SHIM_BINDINGS[alg.name],
                    )
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", inflate_shim_path))
                    continue
                # C-shim state-observer path (state_in -> scalar return)
                # Re-enabled 2026-04-22: CShimField now supports
                # rust_write_template for shim-vs-Rust field-shape mapping,
                # and detect_data_type's hardport now returns i32 matching
                # the binding. The test emitter consumes __stmt__<N> keys
                # from the vector (fully-rendered assignment statements).
                if shim_dll is not None and alg.name in ZLIB_SHIM_OBSERVER_BINDINGS:
                    vectors = fuzz_observer_shim(
                        shim_dll, alg, ZLIB_SHIM_OBSERVER_BINDINGS[alg.name],
                    )
                    _accept(mod, alg, vectors,
                            oracle_tag_for_file("shim", shim_path))
                    continue
                # Byte-buffer transformation path — fn mutates a slice
                # argument or compares two slices. Runs BEFORE the generic
                # pure-reference/catalog paths so zmem* don't fall into
                # the scalar-only fuzz_for_spec codepath that skips them.
                if not generic_subject and alg.name in ZLIB_BYTE_TRANSFORMS:
                    vectors = fuzz_byte_transform(
                        alg, ZLIB_BYTE_TRANSFORMS[alg.name],
                    )
                    _accept(mod, alg, vectors, oracle_tag_for_callable(
                        "pyref", ZLIB_BYTE_TRANSFORMS[alg.name]))
                    continue
                # State-mutator path (fallback): Python reference port
                state_binding = (None if generic_subject
                                 else ZLIB_STATE_MUTATORS.get(alg.name))
                if state_binding is not None:
                    vectors = fuzz_state_mutator(alg, state_binding)
                    _accept(mod, alg, vectors,
                            oracle_tag_for_callable("pyref", state_binding))
                    continue
                # Only skip catalog lookup when catalog vectors will
                # actually be emitted — i.e., the function can consume
                # a byte-slice input. Scalar-arg functions like
                # crc32_combine_gen64 match the catalog by name but
                # can't use the byte-slice tests, so they still need
                # fuzz-generated vectors.
                from alchemist.implementer.test_generator import (
                    _can_accept_byte_slice,
                )
                if _can_accept_byte_slice(alg) and lookup_test_vectors(alg.name):
                    continue
                # Byte-digest hash (SipHash / SHA / HMAC): the return is a
                # Vec<u8> digest, not a scalar — mint {in, [k,] outlen} ->
                # Ok(vec![...]) vectors matching the generated fn's arity.
                sig = subject_sigs.get(alg.name)
                if sig is not None:
                    from alchemist.verifier.auto_config import (
                        classify_digest_shape, fuzz_digest_vectors,
                        classify_cstr_roundtrip, fuzz_cstr_roundtrip_vectors,
                    )
                    if classify_digest_shape(sig) is not None:
                        vectors = fuzz_digest_vectors(dll, alg, sig)
                        _accept(mod, alg, vectors,
                                oracle_tag_for_file("dll", dll_path))
                        continue
                    # Inverse-pair roundtrip decoder (base64_decode etc.): the
                    # generic fuzz_for_spec below can't oracle a `char* f(char*)`
                    # binary-out decoder (random strings aren't valid streams),
                    # so mint vectors by running the paired C ENCODER and require
                    # decode(encode(p)) == p. Must be dispatched here (auto_config
                    # shape), not in fuzz_for_spec.
                    _rt_enc = classify_cstr_roundtrip(sig, subject_sigs)
                    if _rt_enc is not None:
                        vectors = fuzz_cstr_roundtrip_vectors(dll, alg, sig, _rt_enc)
                        _accept(mod, alg, vectors,
                                oracle_tag_for_file("dll", dll_path))
                        continue
                vectors = fuzz_for_spec(
                    dll, alg, subject_bindings,
                    pure_references=subject_pure_refs,
                )
                if alg.name in subject_pure_refs:
                    tag = oracle_tag_for_callable(
                        "pyref", subject_pure_refs[alg.name])
                else:
                    tag = oracle_tag_for_file("dll", dll_path)
                _accept(mod, alg, vectors, tag)
        # Restore any cleared vectors whose oracle produced no replacement —
        # the oracle that minted them isn't available in this environment.
        restored = 0
        for _mod, alg, originals in cleared_for_regen.values():
            if not alg.test_vectors:
                alg.test_vectors = originals
                restored += len(originals)
                console.print(
                    f"  [yellow]fuzz backfill: oracle for {alg.name!r} is "
                    f"unavailable here — kept {len(originals)} previously "
                    f"minted vector(s) instead of silently dropping to zero. "
                    f"Rebuild the shim (subjects/*/shim) to regenerate.[/yellow]"
                )
        if added:
            console.print(f"  [cyan]fuzz backfill: generated {added} vectors[/cyan]")
        # Persist regenerated vectors into the spec checkpoints so they are
        # durable, reviewable artifacts instead of per-run ephemera. Only
        # touched modules are rewritten; authored vectors were never cleared
        # and unavailable-oracle vectors were restored above, so nothing can
        # be lost here.
        if specs_dir is not None and touched_modules:
            persisted = 0
            for mod in specs:
                if mod.name not in touched_modules:
                    continue
                target = Path(specs_dir) / f"{mod.name}.json"
                if not target.exists():
                    continue  # never create spec files the extractor didn't
                target.write_text(mod.model_dump_json(indent=2), encoding="utf-8")
                persisted += 1
            if persisted:
                console.print(
                    f"  [cyan]fuzz backfill: persisted vectors into "
                    f"{persisted} spec checkpoint(s)[/cyan]"
                )

    def _locate_c_dll(self) -> Path | None:
        """Find (or build) the C reference library for fuzz-vector generation.

        zlib keeps its proven hand-placed artifact (verify/zlib1.dll and the
        .so equivalents). Any other subject gets its own oracle COMPILED FROM
        ITS OWN SOURCES into <subject>/.alchemist/oracle/ — the oracle is the
        subject's compiled C, never a stand-in.
        """
        src = getattr(self, "_source_root", None)
        if src is not None and "zlib" not in Path(src).name.lower():
            return self._build_subject_oracle(Path(src))
        candidates = [
            Path("verify/zlib1.dll"),
            Path("verify/zlib.so"),
            Path("verify/libz.so"),
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        return None

    def _build_subject_oracle(self, src: Path) -> Path | None:
        """Compile the subject's .c files into a cached reference library."""
        import sys as _sys
        from alchemist.verifier.auto_ffi import build_c_dll
        # Use the hardened source discovery (skips amalgamation onelua.c, test
        # harnesses ltests.c, and int-main drivers) so a large real library
        # (Lua: 60 files, whole-lib oracle) links without duplicate symbols.
        # A local glob would re-include those and the oracle build would fail.
        from alchemist.verifier.build_c_dll import discover_c_build
        c_sources, _inc = discover_c_build(src)
        if not c_sources:
            return None
        _inc_dirs = list(_inc) if _inc else [src]
        oracle_dir = src / ".alchemist" / "oracle"
        ext = ".dll" if _sys.platform == "win32" else ".so"
        out = oracle_dir / f"lib{src.name}_ref{ext}"
        newest_src = max(f.stat().st_mtime for f in c_sources)
        if out.exists() and out.stat().st_mtime >= newest_src:
            return out.resolve()
        result = build_c_dll(c_sources, out, include_dirs=_inc_dirs)
        if not result.success:
            console.print(
                f"  [yellow]subject oracle build failed: "
                f"{(result.stderr or '')[:300]}[/yellow]"
            )
            return None
        return out.resolve()

    def _build_project_context(
        self, specs: list[ModuleSpec], architecture: CrateArchitecture,
    ) -> str:
        lines = [
            f"## Workspace: {architecture.workspace_name}",
            f"## Crates",
        ]
        for c in architecture.crates:
            lines.append(f"  - {c.name}: {c.description[:150]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cargo helpers
# ---------------------------------------------------------------------------

def _run_cargo_all_targets(path: Path, timeout: int = 300) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["cargo", "check", "--all-targets"],
            cwd=str(path),
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.returncode == 0, r.stderr
    except Exception as e:
        return False, str(e)


def _is_windows_link_lock(stderr: str) -> bool:
    """LNK1104 on Windows means the linker couldn't open a target .exe
    because another process (antivirus, still-exiting test binary) has
    a file lock. Not a real test failure — retry after a brief pause."""
    return "LNK1104" in (stderr or "") or "cannot open file" in (stderr or "")


def _kill_target_zombies(workspace_dir: Path) -> int:
    """Kill any running process whose image lives under workspace_dir/target/.

    libtest can leave worker-process orphans when a cargo test is killed
    or times out. Those orphans hold file locks on the test .exe, causing
    LNK1104 on the next re-link. Proactive kill before each cargo run.
    Only implemented on Windows where this is a real issue.
    """
    if not sys.platform.startswith("win"):
        return 0
    try:
        target = (workspace_dir / "target").resolve()
    except Exception:
        return 0
    target_prefix = str(target).lower()
    try:
        import psutil  # type: ignore
    except ImportError:
        return 0
    killed = 0
    for p in psutil.process_iter(["pid", "exe"]):
        try:
            exe = (p.info.get("exe") or "").lower()
            if exe.startswith(target_prefix):
                p.kill()
                killed += 1
        except Exception:
            pass
    return killed


def _cargo_with_link_retry(argv: list[str], path: Path, timeout: int,
                           max_retries: int = 3) -> tuple[int, str, str]:
    """Run a cargo command with Windows LNK1104 retry-with-backoff.

    Before each attempt, proactively kills any lingering test-binary
    zombies from prior runs that would hold file locks.
    """
    import time
    last = (1, "", "")
    for attempt in range(max_retries):
        _kill_target_zombies(path)
        try:
            r = subprocess.run(
                argv, cwd=str(path),
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
        except Exception as e:
            return 1, "", str(e)
        if r.returncode == 0 or not _is_windows_link_lock(r.stderr):
            return r.returncode, r.stdout, r.stderr
        # Transient link lock; back off 0.5s, 1.5s, 3.0s
        time.sleep(0.5 * (3 ** attempt))
        last = (r.returncode, r.stdout, r.stderr)
    return last


def _run_cargo_fix(path: Path, timeout: int = 180) -> bool:
    """Apply rustc's machine-applicable suggestions via `cargo fix`.

    Deterministic mechanical repair for the common case where the model writes
    algorithmically-correct Rust that fails only on a trivial coercion (e.g.
    `min(usize, u32)` -> `as usize`), a missing `mut`, or an unused import.
    rustfix applies ONLY rustc-verified machine-applicable edits, and the
    byte-exact differential gate still verifies correctness afterward — so this
    can never mask a wrong algorithm, only rescue a mechanically-broken correct
    one. Returns True if cargo fix ran to completion (caller re-checks compile
    to see whether it actually helped)."""
    try:
        r = subprocess.run(
            ["cargo", "fix", "--lib", "--allow-dirty", "--allow-no-vcs",
             "--broken-code"],
            cwd=str(path), capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except Exception:  # noqa: BLE001
        return False
    return r.returncode == 0


def _run_cargo_test(path: Path, timeout: int = 600) -> tuple[bool, str, str]:
    rc, stdout, stderr = _cargo_with_link_retry(
        ["cargo", "test", "--workspace", "--no-fail-fast"], path, timeout,
    )
    return rc == 0, stdout, stderr


def _run_cargo_test_filter(path: Path, test_filter: str | list[str], timeout: int = 300) -> tuple[bool, str, str]:
    """Run `cargo test` filtered to specific name prefixes.

    `test_filter` may be a single string or a list of strings. On Windows,
    cargo only accepts one positional TESTNAME before `--`; multiple
    positional args are rejected. The Rust test binary, however, treats
    non-flag args as OR'd filters. So we pass all filters after `--`.

    Using multiple filters lets us target several non-overlapping test-
    name families simultaneously — important when the short name of fn A
    is a prefix of fn B (e.g., `crc32` vs `crc32_combine_op`). Without
    this, `test_crc32_` would sweep in `test_crc32_combine_op_*` and
    falsely attribute sibling failures to the function under test.
    """
    if isinstance(test_filter, str):
        filters = [test_filter]
    else:
        filters = [f for f in test_filter if f]
    cmd = ["cargo", "test", "--", *filters, "--nocapture"]
    rc, stdout, stderr = _cargo_with_link_retry(cmd, path, timeout)
    return rc == 0, stdout, stderr


def _test_filters_for_fn(fn_name: str) -> list[str]:
    """Return the set of cargo test substring filters that match THIS
    function's tests and no sibling function's tests.

    Test-name schemes in use:
      test_<fn>_vec_<desc>     — catalog vectors
      test_<fn>_spec_<idx>     — spec.test_vectors
      test_<fn>_state_<idx>    — state-mutator vectors
      test_<fn>_observer_<idx> — observer vectors
      test_<fn>_xform_<idx>    — byte-transform vectors (zmem* family)
      test_<fn>_str_<idx>      — str_exact vectors (cbuf_out/NMEA, cstr_out)
      test_<fn>_body_<idx>     — fully-rendered rust_body vectors (tree-builders)
      smoke_<fn>               — legacy smoke test (rare)

    Handles snake-case conversion: spec names like `zlibCompileFlags` are
    rendered as `zlib_compile_flags` in Rust (by _snake in skeleton.py),
    so tests use the snake-cased form. Include BOTH spec-name and
    snake-name filters to cover either case.
    """
    from alchemist.implementer.skeleton import _snake
    snake = _snake(fn_name)
    filters: list[str] = []
    for name in {fn_name, snake}:
        filters.extend([
            f"test_{name}_vec_",
            f"test_{name}_spec_",
            f"test_{name}_state_",
            f"test_{name}_observer_",
            f"test_{name}_xform_",
            f"test_{name}_str_",
            f"test_{name}_body_",
            f"test_{name}_roundtrip_",
            # Stateful-sequence + mutator emitters (test_generator.py): without
            # these the fill loop runs 0 tests for a cipher keystream / alloc op /
            # hash update+final / scalar mutator and FALSELY reports "no test
            # vectors", refusing a function the gate-5 sequence differential
            # actually proves correct. This inflated the refusal metric for every
            # stateful subject (rc4 keystream, bump_alloc op, FNV update/final).
            f"test_{name}_seq_",     # cipher_seq keystream
            f"test_{name}_aseq_",    # alloc_seq op
            f"test_{name}_ainit_",   # alloc_seq init
            f"test_{name}_hinit_",   # hash_seq init
            f"test_{name}_hupd_",    # hash_seq update
            f"test_{name}_hfin_",    # hash_seq final (digest)
            f"test_{name}_mut_",     # scalar_mutator
            f"test_{name}_co_",      # construct_observe (tagged-union DOM ctor/getter)
            f"smoke_{name}",
        ])
    return filters


def _top_lines(text: str, n: int) -> str:
    return "\n".join((text or "").splitlines()[:n])


_ASSERT_LR_RE = re.compile(
    r"left:\s*(\[[^\]]*\])\s*(?:\n|\r\n)?\s*right:\s*(\[[^\]]*\])", re.MULTILINE)


def _distill_vector_divergence(test_output: str) -> str:
    """Turn cargo's noisy `left: [...] / right: [...]` assertion dump into a
    focused, actionable hint: the FIRST output index where the two byte vectors
    diverge, plus a short window around it. A subtle emission-ORDER bug (e.g.
    emitting a code byte before flushing a pending buffer) is invisible in 40
    lines of raw cargo output but obvious as 'agree through index N, then you
    put X where C put Y'. Generalizes to every byte-exact function — the model
    can only fix what it can localize. Returns '' if no left/right pair found."""
    m = _ASSERT_LR_RE.search(test_output or "")
    if not m:
        return ""

    def _parse(arr: str) -> "list[int] | None":
        try:
            return [int(x.strip()) for x in arr.strip("[]").split(",") if x.strip() != ""]
        except ValueError:
            return None

    got = _parse(m.group(1))       # left  = the Rust output under test
    want = _parse(m.group(2))      # right = the C-reference expected output
    if got is None or want is None:
        return ""
    n = min(len(got), len(want))
    idx = next((i for i in range(n) if got[i] != want[i]), n)
    if idx == n and len(got) == len(want):
        return ""  # identical (a different assertion failed)

    lo = max(0, idx - 3)
    hi_g = min(len(got), idx + 5)
    hi_w = min(len(want), idx + 5)
    detail = (
        f"## First divergence at OUTPUT byte index {idx}\n"
        f"- your output length {len(got)}, expected length {len(want)}\n"
    )
    if idx < len(got) and idx < len(want):
        detail += (
            f"- at index {idx}: you emitted {got[idx]}, C emitted {want[idx]}\n")
    elif idx >= len(got):
        detail += f"- your output ends early; C continues with {want[idx]}\n"
    else:
        detail += f"- your output is too long; C stopped, you emitted {got[idx]}\n"
    detail += (
        f"- your bytes   [{lo}..]: {got[lo:hi_g]}\n"
        f"- C ref bytes  [{lo}..]: {want[lo:hi_w]}\n"
    )
    # Same multiset, different order => it is DEFINITELY an emission-ORDER bug,
    # not a wrong value. Say so unambiguously with the concrete fix, because a
    # generic "check your logic" hint does not get the model to restructure the
    # control flow (the smaz_compress flush-before-code case: the model pushes a
    # freshly-matched token before flushing the pending verbatim buffer that C
    # emits first).
    if sorted(got) == sorted(want):
        detail += (
            f"IMPORTANT: your output and C's contain the EXACT SAME bytes, only in a "
            f"DIFFERENT ORDER. This is not a wrong value — it is an EMISSION-ORDER bug. "
            f"When you produce a new token (e.g. a match/code byte), you must FIRST emit "
            f"any pending/buffered output (the verbatim-flush) that C writes before it, "
            f"THEN the new token. Move the pending-buffer flush to run BEFORE you push the "
            f"newly-computed byte at index {idx}. Do not defer the flush to the end of the "
            f"loop iteration.\n"
        )
    else:
        detail += (
            f"The outputs AGREE through index {idx - 1 if idx > 0 else 0}, then diverge. "
            f"If the same values appear in both but in a different ORDER around this "
            f"index, you have an emission-ordering bug (e.g. emitting a token before "
            f"flushing a pending buffer that C flushes first). Fix the order/condition "
            f"at that exact step; do not rewrite the whole function.\n"
        )
    return detail


def _normalize_filled_fn_name(code: str, spec_name: str) -> str:
    """Rename the model's filled function to the skeleton's snake_case name.

    Fed the C source, the model faithfully keeps the C name's casing (e.g.
    `checksum_NMEA`), but the skeleton + generated tests use the snake_case form
    (`checksum_nmea`) — so the tests call a function that doesn't exist and fail.
    Rename `pub fn <X>` to the expected snake name when X maps to the same snake
    form (case/style-only difference); never touches a genuinely different name."""
    if not code:
        return code
    from alchemist.implementer.skeleton import _snake
    want = _snake(spec_name)
    for m in re.finditer(r"\bpub\s+fn\s+([A-Za-z_]\w*)", code):
        got = m.group(1)
        if got != want and (got == spec_name or _snake(got) == want):
            code = re.sub(r"\bfn\s+" + re.escape(got) + r"\b", f"fn {want}", code)
            break
    return code


def _unwrap_llm_schema_leak(s: str) -> str:
    """Strip JSON-schema wrappers an LLM sometimes emits verbatim.

    Maverick occasionally responds with the raw tool_schema JSON
    (`{"type": "object", "properties": {"content": {"value": "..."}}}`)
    instead of the structured output itself. Parse for the embedded
    `pub fn ...` body, or the `value` / `content` leaf.
    """
    if not s or "pub fn" in s and not s.lstrip().startswith("{"):
        return s
    # Attempt JSON parse
    stripped = s.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            import json as _json
            obj = _json.loads(stripped)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            # Schema-leak shape: {"properties": {"content": {"value": "..."}}}
            props = obj.get("properties")
            if isinstance(props, dict):
                for key in ("content", "impl", "fn"):
                    node = props.get(key)
                    if isinstance(node, dict):
                        v = node.get("value") or node.get("default") or node.get("example")
                        if isinstance(v, str) and "pub fn" in v:
                            return v.strip()
            # Direct value: {"content": "pub fn ..."}
            for key in ("content", "impl", "fn"):
                v = obj.get(key)
                if isinstance(v, str) and "pub fn" in v:
                    return v.strip()
    # The whole-blob json.loads above can fail (trailing prose, an unescaped
    # control char, truncation) even when a `content` string IS present and
    # recoverable. Pull the field value out by hand and JSON-decode just that
    # string — this is the correct inverse of the model's encoding and, unlike
    # a raw regex slice, does NOT leave literal `\n` / `\"` in the emitted Rust.
    for key in ("content", "impl", "fn"):
        v = _extract_json_string_field(s, key)
        if isinstance(v, str) and "pub fn" in v:
            return v.strip()
    # Last resort: regex-extract the first `pub fn ...` block, then repair any
    # JSON string escapes that survived (the historical smaz corruption:
    # `pub fn f(){\n    ...` written with a literal backslash-n).
    import re as _re
    m = _re.search(r"pub\s+fn\s+\w+", s)
    if m:
        code = s[m.start():].strip()
        if "\\n" in code or '\\"' in code:
            code = _json_unescape_lenient(code)
        return code
    return s


def _extract_json_string_field(s: str, key: str) -> "str | None":
    """Extract and JSON-decode the string value of `"key": "..."` from a blob
    that failed whole-document json.loads. Scans to the first UNescaped closing
    quote, then json.loads the isolated string literal so every escape (\\n,
    \\", \\\\, \\uXXXX, and a Rust `\\xNN` that was encoded as `\\\\xNN`) is
    decoded exactly as the model intended. Returns None if not found/decodable.
    """
    import json as _json
    import re as _re
    m = _re.search(r'"' + _re.escape(key) + r'"\s*:\s*"', s)
    if not m:
        return None
    i = m.end()
    buf: list[str] = []
    while i < len(s):
        c = s[i]
        if c == "\\":
            if i + 1 < len(s):
                buf.append(s[i]); buf.append(s[i + 1]); i += 2; continue
            buf.append(c); i += 1; continue
        if c == '"':
            break
        buf.append(c); i += 1
    try:
        return _json.loads('"' + "".join(buf) + '"')
    except Exception:  # noqa: BLE001
        return None


def _json_unescape_lenient(t: str) -> str:
    """Best-effort repair of JSON string escapes that leaked into emitted Rust
    when json.loads failed outright. Left-to-right so an escaped backslash is
    consumed as a pair: a validly-encoded Rust byte literal `\\\\xNN` becomes
    `\\xNN` (preserved), while a stray JSON `\\n` becomes a real newline.
    Unknown escapes (e.g. a lone `\\x`) keep their backslash untouched, so Rust
    `b"\\x02"` literals are never corrupted."""
    out: list[str] = []
    i = 0
    simple = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}
    while i < len(t):
        c = t[i]
        if c == "\\" and i + 1 < len(t) and t[i + 1] in simple:
            out.append(simple[t[i + 1]]); i += 2; continue
        out.append(c); i += 1
    return "".join(out)
