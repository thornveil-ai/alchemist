"""Whole-program differential oracle — the verification gate for C→Rust
translations that CANNOT be checked per-function.

Alchemist's per-function differential (FFI-call the C, FFI-call the Rust, compare)
only works when a function has a clean byte-in/byte-out interface. A cyclic core
over shared mutable state — a Lua interpreter's ~600 functions over `lua_State`,
an autopilot's flight loop over its vehicle state — has no such interface: you
cannot FFI-marshal a `lua_State`. Such programs are verified END-TO-END instead:

    run an identical INPUT CORPUS through the compiled C reference AND the
    translated Rust build, and require byte-identical OBSERVABLE behavior
    (stdout + stderr + exit status).

Byte-exact-or-refused, at the whole-program level. This is subject-agnostic:
the reference/candidate build+run commands and the corpus are supplied per
subject (Lua: `lua <script>` over `*.lua`; PX4: SITL over flight scenarios).
It is the general capability the converter needs to translate whole programs,
not a Lua-specific script.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class E2ECase:
    """One corpus input and both sides' captured observable output."""
    name: str
    passed: bool
    detail: str = ""


@dataclass
class E2EResult:
    passed: bool
    total: int
    npass: int
    cases: list[E2ECase] = field(default_factory=list)

    def summary(self) -> str:
        return f"e2e oracle: {self.npass}/{self.total} corpus inputs byte-identical"


@dataclass
class E2EOracleSpec:
    """How to run a whole-program differential for one subject.

    `reference_cmd` / `candidate_cmd` are argv lists; the literal token
    ``"{input}"`` in either is replaced by each corpus input path. Everything
    else (which binary, extra flags, working dir) is subject-supplied, so the
    same gate serves Lua, PX4, or any whole program.
    """
    name: str
    reference_cmd: list[str]   # e.g. ["/path/lua_ref", "{input}"]
    candidate_cmd: list[str]   # e.g. ["/path/rust-lua", "{input}"]
    corpus: list[Path]         # the input files
    cwd: str | None = None
    timeout: int = 30
    # Compare mode: "observable" = stdout+stderr+exitcode (default); "stdout" = stdout only.
    compare: str = "observable"

    def _run(self, cmd: list[str], inp: Path) -> tuple[bytes, int]:
        argv = [inp.as_posix() if tok == "{input}" else tok for tok in cmd]
        try:
            p = subprocess.run(
                argv, cwd=self.cwd, capture_output=True,
                timeout=self.timeout,
            )
            out = p.stdout if self.compare == "stdout" else p.stdout + p.stderr
            return out, p.returncode
        except subprocess.TimeoutExpired:
            return b"<timeout>", -1
        except FileNotFoundError as e:
            return f"<exec error: {e}>".encode(), -2


def run_e2e_oracle(spec: E2EOracleSpec) -> E2EResult:
    """Run every corpus input through reference and candidate; diff observable
    output. A single mismatch fails the whole gate (byte-exact-or-refused)."""
    cases: list[E2ECase] = []
    npass = 0
    for inp in spec.corpus:
        ref_out, ref_rc = spec._run(spec.reference_cmd, inp)
        cand_out, cand_rc = spec._run(spec.candidate_cmd, inp)
        rc_ok = spec.compare == "stdout" or ref_rc == cand_rc
        if ref_out == cand_out and rc_ok:
            npass += 1
            cases.append(E2ECase(inp.name, True))
        else:
            detail = _first_diff(ref_out, cand_out, ref_rc, cand_rc)
            cases.append(E2ECase(inp.name, False, detail))
    return E2EResult(
        passed=(npass == len(spec.corpus) and len(spec.corpus) > 0),
        total=len(spec.corpus),
        npass=npass,
        cases=cases,
    )


def _first_diff(ref: bytes, cand: bytes, ref_rc: int, cand_rc: int) -> str:
    if ref_rc != cand_rc:
        return f"exit {cand_rc} != reference {ref_rc}"
    # Find the first differing line for a compact, actionable message.
    rl = ref.splitlines()
    cl = cand.splitlines()
    for i in range(min(len(rl), len(cl))):
        if rl[i] != cl[i]:
            return (f"line {i+1}: got {cl[i][:60]!r} "
                    f"!= ref {rl[i][:60]!r}")
    if len(rl) != len(cl):
        return f"line count {len(cl)} != reference {len(rl)}"
    return "output differs"


def spec_from_corpus_dir(
    name: str,
    reference_bin: str | Path,
    candidate_bin: str | Path,
    corpus_dir: str | Path,
    glob: str = "*",
    **kw,
) -> E2EOracleSpec:
    """Convenience: build a spec that runs `<bin> <input>` for every file in a
    corpus directory. The general shape for interpreters/tools that take an
    input file (Lua: reference=lua, candidate=rust-lua, glob='*.lua')."""
    corpus = sorted(Path(corpus_dir).glob(glob))
    return E2EOracleSpec(
        name=name,
        reference_cmd=[str(reference_bin), "{input}"],
        candidate_cmd=[str(candidate_bin), "{input}"],
        corpus=corpus,
        **kw,
    )
