"""Item 4 — harden autonomy + packaging (the 'ship it' layer).

Three things a one-stop shop needs to be trusted unattended:

  translate_safely — crash-proof: ANY exception on one function becomes a 'refused'
                     verdict with the reason, so a single bad function never kills a
                     whole-project run. The pipeline degrades honestly, never dies.

  ProjectManifest  — aggregate every function's outcome into ONE signed, content-
                     hashed project record: an honest per-function dashboard
                     (verified / partial / refused-with-reason) an accreditor reads.

  emit_workspace   — a real cargo workspace tying the verified crates together, so
                     the deliverable is a buildable Rust project, not a pile of files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class FunctionOutcome:
    function: str
    verdict: str                      # "verified" | "partial" | "refused"
    sha256: str | None = None         # the function's verification-receipt digest
    memory_safe: bool | None = None
    miri: bool | None = None
    cwes: list = field(default_factory=list)
    reason: str = ""                  # why, for partial/refused


def translate_safely(name: str, fn: Callable[[], FunctionOutcome]) -> FunctionOutcome:
    """Run one function's translation; convert any crash into an honest 'refused'."""
    try:
        return fn()
    except Exception as e:                    # noqa: BLE001 - the whole point
        return FunctionOutcome(name, "refused", reason="%s: %s" % (type(e).__name__, str(e)[:160]))


@dataclass
class ProjectManifest:
    project: str
    functions: list = field(default_factory=list)   # FunctionOutcome
    tool: str = "alchemist"

    def add(self, outcome: FunctionOutcome) -> None:
        self.functions.append(outcome)

    def summary(self) -> dict:
        by: dict[str, int] = {}
        for f in self.functions:
            by[f.verdict] = by.get(f.verdict, 0) + 1
        total = len(self.functions)
        return {"total": total, "by_verdict": dict(sorted(by.items())),
                "verified_fraction": round(by.get("verified", 0) / total, 3) if total else 0.0}

    def canonical(self) -> str:
        body = {"project": self.project, "tool": self.tool,
                "functions": sorted((asdict(f) for f in self.functions),
                                    key=lambda d: d["function"])}
        return json.dumps(body, sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def attest(self) -> dict:
        """Signed project manifest: summary + per-fn dashboard + integrity digest."""
        out = {"project": self.project, "summary": self.summary(),
               "functions": [asdict(f) for f in self.functions], "sha256": self.digest()}
        try:
            from signet import sign as _sign   # type: ignore
            out["signature"] = _sign(self.canonical())
        except Exception:
            out["signature"] = None
        return out


def emit_workspace(root: Path, crate_dirs: list[Path]) -> Path:
    """Write a cargo workspace Cargo.toml tying the verified member crates together."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    members = ",\n".join('    "%s"' % Path(c).name for c in crate_dirs)
    toml = "[workspace]\nresolver = \"2\"\nmembers = [\n%s\n]\n" % members
    (root / "Cargo.toml").write_text(toml)
    return root / "Cargo.toml"
