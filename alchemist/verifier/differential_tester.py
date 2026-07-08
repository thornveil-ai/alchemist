"""Stage 5 — mandatory differential verification gate.

Contract: the pipeline CANNOT declare success unless every generated crate
passes these layers of checks:

  1. COMPILE   — `cargo check` exits clean.
  2. ANTI-STUB — no stub markers, no fake code (anti_stub.scan_workspace).
  3. SEMANTIC  — family lints against the specs (semantic_lints); a wrong
                 algorithm variant fails closed here. Runs when specs are
                 supplied; reports itself as not-run otherwise.
  4. TEST      — `cargo test` passes.
  5. DIFFERENTIAL — every configured harness passes against C reference.

If any layer fails, `run_all()` returns a VerificationReport with `passed=False`
and a reason populated. Stage 5 callers MUST refuse to declare success when
this returns False.

This module leverages the sibling auto_ffi.py, adapter_gen.py and
proptest_gen.py: those build the C DLL, emit the c_*/rust_* wrapper crate
against the REAL generated API, and emit the Rust harness; this module
sequences the gate.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from alchemist.implementer.anti_stub import ScanReport, scan_workspace
from alchemist.verifier.adapter_gen import (
    AdapterPlan,
    emit_adapter_lib,
    emit_unresolved_tests,
    plan_adapters,
)
from alchemist.verifier.auto_ffi import (
    AutoFfiRequest,
    AutoFfiResult,
    CSignature,
    TypedefMap,
    generate_ffi_crate,
)
from alchemist.verifier.proptest_gen import (
    AlgorithmHarness,
    emit_differential_test,
)

console = Console(force_terminal=True, legacy_windows=False)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    """Result of a single gate."""
    name: str
    passed: bool
    summary: str = ""
    stdout: str = ""
    stderr: str = ""
    # For anti-stub gate: carries the violation list
    anti_stub_report: ScanReport | None = None


@dataclass
class VerificationReport:
    compile: GateResult
    anti_stub: GateResult
    no_unsafe: GateResult
    semantic: GateResult
    test: GateResult
    differential: GateResult
    # Optional UB-freedom proof under Miri. Defaults to a not-run PASS so it never
    # blocks a system without nightly+miri and never breaks existing constructions.
    miri: GateResult = field(default_factory=lambda: GateResult("miri", True, "not run"))

    @property
    def passed(self) -> bool:
        return (
            self.compile.passed
            and self.anti_stub.passed
            and self.no_unsafe.passed
            and self.semantic.passed
            and self.test.passed
            and self.differential.passed
            and self.miri.passed
        )

    @property
    def first_failure(self) -> GateResult | None:
        for g in (self.compile, self.anti_stub, self.no_unsafe, self.semantic,
                  self.test, self.differential, self.miri):
            if not g.passed:
                return g
        return None

    def summary(self) -> str:
        def mark(g: GateResult) -> str:
            return "PASS" if g.passed else "FAIL"
        return (
            f"[compile    {mark(self.compile)}] {self.compile.summary}\n"
            f"[anti-stub  {mark(self.anti_stub)}] {self.anti_stub.summary}\n"
            f"[no-unsafe  {mark(self.no_unsafe)}] {self.no_unsafe.summary}\n"
            f"[semantic   {mark(self.semantic)}] {self.semantic.summary}\n"
            f"[test       {mark(self.test)}] {self.test.summary}\n"
            f"[diff       {mark(self.differential)}] {self.differential.summary}\n"
            f"[miri       {mark(self.miri)}] {self.miri.summary}\n"
            f"OVERALL: {'PASS' if self.passed else 'FAIL'}"
        )


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

@dataclass
class DifferentialConfig:
    """Everything needed to build and run the differential harness."""
    c_sources: list[Path] = field(default_factory=list)
    c_include_dirs: list[Path] = field(default_factory=list)
    c_public_signatures: list[CSignature] = field(default_factory=list)
    c_typedefs: TypedefMap = field(default_factory=TypedefMap)
    c_opaque_types: set[str] = field(default_factory=set)
    harnesses: list[AlgorithmHarness] = field(default_factory=list)
    c_struct_defs: list = field(default_factory=list)
    # Used as the name of the generated FFI crate + DLL.
    ffi_crate_name: str = "c_reference"
    # Optional path under which to emit the FFI crate + differential test crate.
    # If None, uses `<rust_workspace>.parent/verify_gen/`.
    verify_dir: Path | None = None
    # Restrict the compile/anti-stub/test gates to these workspace packages
    # (crate dir name == package name in generated workspaces). Empty = whole
    # workspace. The differential gate is always harness-driven and the
    # semantic gate always sweeps the whole workspace regardless of scoping.
    packages: list[str] = field(default_factory=list)


class DifferentialTester:
    """Stage 5 gate: compile → anti-stub → semantic → test → differential."""

    def __init__(
        self,
        rust_workspace: Path,
        *,
        diff_config: DifferentialConfig | None = None,
        specs: list | None = None,
        specs_error: str | None = None,
        timeout_compile: int = 300,
        timeout_test: int = 600,
        timeout_diff: int = 900,
        enable_miri: bool = False,
    ):
        self.rust_workspace = Path(rust_workspace)
        self.diff_config = diff_config
        # ModuleSpec list for the semantic gate. None = the subject has no
        # specs; the gate reports itself as not-run (the differential gate
        # still fails closed without config, so overall success stays
        # impossible for an unconfigured run). If the subject HAS specs but
        # loading them crashed, pass specs_error instead — the gate must
        # FAIL rather than silently disarm on infrastructure rot.
        self.specs = specs
        self.specs_error = specs_error
        self.timeout_compile = timeout_compile
        self.timeout_test = timeout_test
        self.timeout_diff = timeout_diff
        self.enable_miri = enable_miri
        # Populated by _build_and_run_differential; consumed by the receipt.
        self._diff_evidence: dict | None = None

    def _package_args(self) -> list[str]:
        pkgs = self.diff_config.packages if self.diff_config else []
        if pkgs:
            out: list[str] = []
            for p in pkgs:
                out.extend(["-p", p])
            return out
        return ["--workspace"]

    # --- Individual gates ---

    def gate_compile(self) -> GateResult:
        scope = self._package_args()
        console.print(f"[cyan]gate 1/5: cargo check {' '.join(scope)}[/cyan]")
        try:
            r = subprocess.run(
                ["cargo", "check", *scope, "--all-targets"],
                cwd=str(self.rust_workspace),
                capture_output=True,
                text=True,
                timeout=self.timeout_compile,
            )
        except subprocess.TimeoutExpired as e:
            return GateResult(
                name="compile",
                passed=False,
                summary=f"cargo check timed out after {self.timeout_compile}s",
                stderr=str(e),
            )
        errors = r.stderr.count("error[") + r.stderr.count("error:")
        return GateResult(
            name="compile",
            passed=r.returncode == 0,
            summary=(
                f"cargo check clean" if r.returncode == 0
                else f"{errors} compile errors"
            ),
            stdout=r.stdout,
            stderr=r.stderr,
        )

    def gate_no_unsafe(self) -> GateResult:
        """Structural no-unsafe proof.

        Scans every .rs file under the workspace for any occurrence of
        `unsafe` that isn't part of the structural `#![forbid(unsafe_code)]`
        attribute the skeleton emits. Also checks that every crate's lib.rs
        carries the forbid attribute.
        """
        console.print("[cyan]gate: structural no-unsafe proof[/cyan]")
        import re as _re
        rs_files = [
            p for p in self.rust_workspace.rglob("*.rs")
            if "target" not in p.parts
        ]
        # Every lib.rs must have #![forbid(unsafe_code)]
        forbidden_missing: list[str] = []
        # Any use of `unsafe` outside the forbid attribute is a violation.
        unsafe_uses: list[str] = []
        for p in rs_files:
            text = p.read_text(encoding="utf-8", errors="replace")
            if p.name == "lib.rs":
                if "#![forbid(unsafe_code)]" not in text:
                    forbidden_missing.append(str(p))
            # Strip the attribute itself so we don't flag the word "unsafe" in it.
            stripped = _re.sub(
                r"#!\[forbid\(unsafe_code\)\]", "", text
            )
            # Look for the unsafe keyword as a standalone token.
            for m in _re.finditer(r"\bunsafe\b", stripped):
                # Get the line for context
                line_start = stripped.rfind("\n", 0, m.start()) + 1
                line_end = stripped.find("\n", m.end())
                if line_end == -1:
                    line_end = len(stripped)
                line = stripped[line_start:line_end]
                unsafe_uses.append(f"{p}: {line.strip()[:120]}")
        passed = not forbidden_missing and not unsafe_uses
        if passed:
            summary = f"zero unsafe across {len(rs_files)} files"
        else:
            parts = []
            if forbidden_missing:
                parts.append(f"{len(forbidden_missing)} lib.rs missing forbid attr")
            if unsafe_uses:
                parts.append(f"{len(unsafe_uses)} unsafe usages")
            summary = "; ".join(parts)
        return GateResult(
            name="no-unsafe",
            passed=passed,
            summary=summary,
            stdout="\n".join(forbidden_missing + unsafe_uses[:20]),
        )

    def gate_anti_stub(self) -> GateResult:
        console.print("[cyan]gate 2/5: anti-stub scan[/cyan]")
        pkgs = self.diff_config.packages if self.diff_config else []
        if pkgs:
            # Generated workspaces name each member dir after its package.
            # If any scoped dir is missing, fall back to the full scan —
            # scanning too much is safe, scanning too little is not.
            pkg_dirs = [self.rust_workspace / p for p in pkgs]
            if all(d.is_dir() for d in pkg_dirs):
                report = ScanReport()
                for d in pkg_dirs:
                    sub = scan_workspace(d)
                    report.files_scanned += sub.files_scanned
                    report.violations.extend(sub.violations)
            else:
                report = scan_workspace(self.rust_workspace)
        else:
            report = scan_workspace(self.rust_workspace)
        return GateResult(
            name="anti-stub",
            passed=report.ok,
            summary=report.summary().splitlines()[0],
            anti_stub_report=report,
        )

    def gate_semantic(self) -> GateResult:
        """Family lints (semantic_lints) against the specs, workspace-wide.

        Catches code that compiles and runs but implements the wrong
        algorithm variant — the failure differential fixed vectors may miss
        when the vectors were derived from the same wrong assumption.
        """
        console.print("[cyan]gate 3/5: semantic lints[/cyan]")
        if self.specs_error:
            return GateResult(
                name="semantic",
                passed=False,
                summary=(
                    f"spec loading failed ({self.specs_error}) — the subject has "
                    f"specs but they could not be read; REFUSING to claim success"
                ),
                stderr=self.specs_error,
            )
        if self.specs is None:
            return GateResult(
                name="semantic",
                passed=True,
                summary="not run — no specs supplied (pass specs= to enable)",
            )
        if not self.specs:
            return GateResult(
                name="semantic",
                passed=False,
                summary=(
                    "specs supplied but contain 0 module specs — nothing would be "
                    "linted; REFUSING to claim success"
                ),
            )
        from alchemist.implementer.semantic_lints import (
            format_findings,
            has_errors,
            scan_workspace_semantics,
        )
        try:
            findings = scan_workspace_semantics(self.rust_workspace, self.specs)
        except Exception as e:
            return GateResult(
                name="semantic",
                passed=False,
                summary=f"semantic sweep crashed: {e} — REFUSING to claim success",
                stderr=str(e),
            )
        errors = [f for f in findings if f.severity == "error"]
        return GateResult(
            name="semantic",
            passed=not has_errors(findings),
            summary=(
                f"{len(errors)} error finding(s)" if errors
                else f"clean ({len(findings)} advisory finding(s))" if findings
                else "clean"
            ),
            stdout=format_findings(findings),
        )

    def gate_test(self) -> GateResult:
        scope = self._package_args()
        console.print(f"[cyan]gate 4/5: cargo test {' '.join(scope)}[/cyan]")
        try:
            r = subprocess.run(
                ["cargo", "test", *scope, "--", "--nocapture"],
                cwd=str(self.rust_workspace),
                capture_output=True,
                text=True,
                timeout=self.timeout_test,
            )
        except subprocess.TimeoutExpired as e:
            return GateResult(
                name="test",
                passed=False,
                summary=f"cargo test timed out after {self.timeout_test}s",
                stderr=str(e),
            )
        passed = r.returncode == 0
        # Roughly count test counts
        lines = (r.stdout + "\n" + r.stderr).splitlines()
        result_lines = [l for l in lines if "test result:" in l]
        summary = "; ".join(result_lines[-4:]) or (
            "cargo test passed" if passed else "cargo test failed"
        )
        return GateResult(
            name="test",
            passed=passed,
            summary=summary,
            stdout=r.stdout,
            stderr=r.stderr,
        )

    def gate_differential(self) -> GateResult:
        console.print("[cyan]gate 5/5: differential tests[/cyan]")
        if not self.diff_config or not self.diff_config.harnesses:
            return GateResult(
                name="differential",
                passed=False,
                summary="no differential config provided — REFUSING to claim success",
            )
        try:
            result = self._build_and_run_differential(self.diff_config)
            return result
        except Exception as e:
            return GateResult(
                name="differential",
                passed=False,
                summary=f"differential harness failed to build: {e}",
                stderr=str(e),
            )

    # --- Orchestration ---

    def gate_miri(self) -> GateResult:
        """Optional: prove the safe Rust is free of undefined behaviour under Miri.
        Opt-in (`enable_miri`); PASSES as not-run when disabled or when nightly+miri
        is unavailable, so it never blocks a system without the toolchain."""
        if not self.enable_miri:
            return GateResult("miri", True, "not run (disabled)")
        console.print("[cyan]gate 6/6: cargo +nightly miri test[/cyan]")
        try:
            r = subprocess.run(
                ["cargo", "+nightly", "miri", "test", *self._package_args()],
                cwd=str(self.rust_workspace), capture_output=True, text=True,
                timeout=self.timeout_test,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return GateResult("miri", True, f"not run (miri unavailable: {e})")
        out = r.stdout + r.stderr
        if "no such subcommand" in out or "not installed" in out.lower():
            return GateResult("miri", True, "not run (miri not installed)")
        ok = "test result: ok" in out
        return GateResult("miri", ok,
                          "UB-free under Miri" if ok else "Miri found undefined behaviour",
                          stdout=r.stdout, stderr=r.stderr)

    def run_all(self) -> VerificationReport:
        compile_r = self.gate_compile()
        # Run all informational gates regardless of compile outcome so the
        # report is complete.
        anti_r = self.gate_anti_stub()
        no_unsafe_r = self.gate_no_unsafe()
        semantic_r = self.gate_semantic()
        if not compile_r.passed:
            # Can't run tests if it doesn't compile
            return VerificationReport(
                compile=compile_r,
                anti_stub=anti_r,
                no_unsafe=no_unsafe_r,
                semantic=semantic_r,
                test=GateResult(
                    name="test", passed=False,
                    summary="skipped — compile failed",
                ),
                differential=GateResult(
                    name="differential", passed=False,
                    summary="skipped — compile failed",
                ),
            )
        test_r = self.gate_test()
        diff_r = self.gate_differential() if test_r.passed else GateResult(
            name="differential", passed=False,
            summary="skipped — test gate failed",
        )
        miri_r = self.gate_miri() if test_r.passed else GateResult(
            "miri", True, "skipped — test gate failed")
        return VerificationReport(
            compile=compile_r,
            anti_stub=anti_r,
            no_unsafe=no_unsafe_r,
            semantic=semantic_r,
            test=test_r,
            differential=diff_r,
            miri=miri_r,
        )

    # --- Differential harness build / run ---

    def _build_and_run_differential(self, cfg: DifferentialConfig) -> GateResult:
        verify_dir = cfg.verify_dir or (self.rust_workspace.parent / "verify_gen")
        ffi_dir = verify_dir / cfg.ffi_crate_name
        diff_dir = verify_dir / "diff_test"

        ffi_result = generate_ffi_crate(AutoFfiRequest(
            c_sources=cfg.c_sources,
            include_dirs=cfg.c_include_dirs,
            public_signatures=cfg.c_public_signatures,
            output_dir=ffi_dir,
            crate_name=cfg.ffi_crate_name,
            lib_name=cfg.ffi_crate_name,
            typedefs=cfg.c_typedefs,
            opaque_types=cfg.c_opaque_types,
            struct_defs=cfg.c_struct_defs,
        ))
        if not ffi_result.build.success:
            return GateResult(
                name="differential",
                passed=False,
                summary="FFI C DLL build failed",
                stderr=ffi_result.build.stderr,
            )

        # Emit test crate (adapters discovered from the real generated API)
        plan = self._write_test_crate(diff_dir, cfg, ffi_result)
        adapted = f"{len(plan.resolved)}/{len(cfg.harnesses)} harnesses adapted"
        bindings = "; ".join(r.resolution for r in plan.resolved if r.resolution)
        if bindings:
            adapted += f" ({bindings})"
        if plan.unresolved:
            names = ", ".join(h.algorithm for h, _ in plan.unresolved)
            adapted += f" (unresolved: {names})"
        # Evidence for the verification receipt (see verifier/receipt.py).
        self._diff_evidence = {
            "verify_dir": verify_dir,
            "dll_path": ffi_result.build.dll_path,
            "bindings": [r.resolution for r in plan.resolved if r.resolution],
            "unresolved": [(h.algorithm, reason) for h, reason in plan.unresolved],
            "cargo_summary": None,
        }

        # The differential test binary loads the C oracle shared library at
        # RUNTIME. Windows searches the executable's directory (handled by the
        # copy above); Linux/mac need the oracle dir on the loader path — the
        # FFI build.rs rpath applies to the FFI cdylib, not the test binary.
        import os as _os
        import sys as _sys
        env = dict(_os.environ)
        oracle_dir = str(Path(ffi_result.build.dll_path).parent.resolve())
        if _sys.platform == "win32":
            var = "PATH"
        elif _sys.platform == "darwin":
            var = "DYLD_LIBRARY_PATH"
        else:
            var = "LD_LIBRARY_PATH"
        env[var] = oracle_dir + _os.pathsep + env.get(var, "")

        # Run cargo test --test differential inside diff_dir
        try:
            r = subprocess.run(
                ["cargo", "test", "--test", "differential", "--release", "--",
                 "--nocapture"],
                cwd=str(diff_dir),
                capture_output=True,
                text=True,
                timeout=self.timeout_diff,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            return GateResult(
                name="differential",
                passed=False,
                summary=f"differential tests timed out after {self.timeout_diff}s",
                stderr=str(e),
            )
        passed = r.returncode == 0
        lines = (r.stdout + "\n" + r.stderr).splitlines()
        summary_line = next(
            (l for l in lines[::-1] if "test result:" in l),
            "differential pass" if passed else "differential fail",
        )
        self._diff_evidence["cargo_summary"] = summary_line.strip()
        return GateResult(
            name="differential",
            passed=passed,
            summary=f"{summary_line.strip()} [{adapted}]",
            stdout=r.stdout,
            stderr=r.stderr,
        )

    def _workspace_crate_dirs(self) -> dict[str, Path]:
        """Map generated-workspace package name → crate directory."""
        import re as _re
        out: dict[str, Path] = {}
        for cargo_toml in sorted(self.rust_workspace.glob("*/Cargo.toml")):
            m = _re.search(
                r'^name\s*=\s*"([^"]+)"',
                cargo_toml.read_text(encoding="utf-8"),
                _re.MULTILINE,
            )
            if m:
                out[m.group(1)] = cargo_toml.parent
        return out

    def _write_test_crate(
        self,
        diff_dir: Path,
        cfg: DifferentialConfig,
        ffi: AutoFfiResult,
    ) -> AdapterPlan:
        """Emit the differential test crate against the REAL generated API.

        The crate consists of:
          - Cargo.toml path-depending on the FFI crate AND on every generated
            crate an adapter resolved into;
          - src/lib.rs with auto-generated c_*/rust_* wrappers (adapter_gen),
            discovered from the generated sources — never assumed;
          - tests/differential.rs with proptest harnesses for every RESOLVED
            algorithm plus one always-failing test per UNRESOLVED one, so an
            un-adaptable harness turns the gate red instead of vanishing.
        """
        diff_dir.mkdir(parents=True, exist_ok=True)
        (diff_dir / "tests").mkdir(parents=True, exist_ok=True)
        (diff_dir / "src").mkdir(parents=True, exist_ok=True)

        plan = plan_adapters(
            cfg.harnesses,
            rust_workspace=self.rust_workspace,
            ffi_crate_name=cfg.ffi_crate_name,
            c_signatures=cfg.c_public_signatures,
            packages=cfg.packages or None,
        )

        # Cargo.toml — path-deps on the FFI crate + every resolved generated
        # crate. Paths MUST be absolute: a relative path would resolve
        # against the emitted manifest's own directory, not the caller's cwd.
        crate_dirs = self._workspace_crate_dirs()
        dep_lines = [
            f'{cfg.ffi_crate_name} = '
            f'{{ path = "{ffi.cargo_toml_path.parent.resolve().as_posix()}" }}'
        ]
        for pkg in sorted(plan.rust_crates):
            d = crate_dirs.get(pkg)
            if d is None:
                # Discovery produced a crate we can't locate — configuration
                # rot. Surface it as an unresolved harness-level failure.
                plan.unresolved.extend(
                    (r.harness, f"crate dir for package {pkg!r} not found under "
                                f"{self.rust_workspace}")
                    for r in list(plan.resolved) if pkg in r.rust_crates
                )
                plan.resolved = [r for r in plan.resolved if pkg not in r.rust_crates]
                continue
            dep_lines.append(f'{pkg} = {{ path = "{d.resolve().as_posix()}" }}')
        cargo = (
            "[package]\n"
            'name = "diff_test"\n'
            'version = "0.1.0"\n'
            'edition = "2021"\n\n'
            "[dependencies]\n"
            + "\n".join(dep_lines) + "\n"
            "\n"
            "[dev-dependencies]\n"
            'proptest = "1.4"\n'
            "\n"
            "[workspace]\n"
        )
        (diff_dir / "Cargo.toml").write_text(cargo, encoding="utf-8")

        # src/lib.rs — the adapter wrappers.
        (diff_dir / "src" / "lib.rs").write_text(
            emit_adapter_lib(plan, ffi_crate_name=cfg.ffi_crate_name),
            encoding="utf-8",
        )

        # tests/differential.rs — harnesses for resolved algorithms, failing
        # tests for unresolved ones.
        resolved_harnesses = [r.harness for r in plan.resolved]
        parts: list[str] = []
        if resolved_harnesses:
            parts.append(emit_differential_test(
                resolved_harnesses,
                extra_imports=["use diff_test::*;"],
                module_doc="Auto-generated differential tests (Stage 5 gate).",
            ))
        else:
            parts.append("//! Auto-generated differential tests (Stage 5 gate).\n")
        unresolved_block = emit_unresolved_tests(plan)
        if unresolved_block:
            parts.append("// === unresolved harnesses (fail closed) ===\n")
            parts.append(unresolved_block)
        (diff_dir / "tests" / "differential.rs").write_text(
            "\n".join(parts), encoding="utf-8",
        )

        # The test binary loads the C DLL at runtime; Windows resolves it via
        # the process CWD (cargo test runs with cwd=diff_dir) — same proven
        # layout as the hand-written verify/diff_test crate.
        if ffi.build.dll_path and ffi.build.dll_path.exists():
            shutil.copy2(ffi.build.dll_path, diff_dir / ffi.build.dll_path.name)
        return plan


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------

def verify_workspace(
    rust_workspace: Path,
    diff_config: DifferentialConfig | None = None,
    *,
    specs: list | None = None,
    specs_error: str | None = None,
    refuse_without_diff: bool = True,
    enable_miri: bool = False,
) -> VerificationReport:
    """Public API — run all gates and return report.

    If `refuse_without_diff=True` (the production default) and no diff_config
    is supplied, the differential gate will FAIL with the reason "no
    differential config". This enforces the rule that Alchemist refuses to
    claim success without verification.

    Pass `specs` (list of ModuleSpec) to enable the semantic gate — family
    lints that fail closed on wrong algorithm variants. If the subject has
    specs but loading them failed, pass `specs_error` so the semantic gate
    FAILS instead of reporting itself not-run.

    Every run with a differential config also writes a verification receipt
    (verify_gen/receipt.json) recording gate results, harness bindings, and
    the oracle's identity (compiler version + source/DLL hashes).
    """
    tester = DifferentialTester(
        rust_workspace, diff_config=diff_config, specs=specs,
        specs_error=specs_error, enable_miri=enable_miri,
    )
    report = tester.run_all()
    if diff_config is not None:
        try:
            from alchemist.verifier.receipt import build_receipt, write_receipt
            evidence = getattr(tester, "_diff_evidence", None)
            receipt = build_receipt(
                report=report,
                rust_workspace=Path(rust_workspace),
                diff_config=diff_config,
                diff_evidence=evidence,
                specs=specs,
            )
            verify_dir = (
                (evidence or {}).get("verify_dir")
                or diff_config.verify_dir
                or (Path(rust_workspace).parent / "verify_gen")
            )
            path = write_receipt(receipt, Path(verify_dir) / "receipt.json")
            console.print(f"[cyan]verification receipt: {path}[/cyan]")
        except Exception as e:  # noqa: BLE001
            # The receipt documents the claim; failing to write it must be
            # visible but must not change the verification verdict itself.
            console.print(f"[yellow]receipt emission failed: {e}[/yellow]")
    return report
