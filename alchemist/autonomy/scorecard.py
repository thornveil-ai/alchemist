"""M1 autonomy scorecard: inventory + classify the human-supplied knowledge the
pipeline currently relies on to translate a subject (default: zlib).

Framing: **autonomy debt**. To translate zlib byte-exact *today*, the pipeline
leans on artifacts a human authored — hand-written oracle shims, human-ported
Rust bodies, hand-specified type overrides, curated references. Each is a crutch
M1 must remove by auto-synthesizing the equivalent. This tool counts them,
classifies each by workstream (WS1..WS7 of PATH_TO_AUTONOMY.md), and renders the
result as a checklist so progress is measurable run-over-run.

It is deliberately a *static* inventory of baked-in human knowledge — a strong,
actionable proxy for "how far from push-button." Dynamic in-run interventions
(diagnosing a bug, hand-writing a control-flow skeleton) are harder to measure
statically; WS4's repair loop will make those observable as they get automated.

Run:  python -m alchemist.autonomy.scorecard [--subject zlib] [--json]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FN_RE = re.compile(r"^\s*(?:pub\s+)?(?:unsafe\s+)?fn\s+\w+\s*[<(]", re.MULTILINE)
_SHIM_RE = re.compile(
    r"\b(?:void|int|unsigned|uint\d+_t|size_t|uLong|long|char|double|float|z_\w+)"
    r"\s+\**\s*(shim_[a-z0-9_]+)\s*\(",
)


@dataclass
class DebtCategory:
    key: str
    workstream: str          # e.g. "WS1"
    title: str
    count: int               # number of human-supplied artifacts
    unit: str                # "shims", "fns", "overrides", ...
    detail: str = ""
    automated: bool = False   # True => retired debt (now auto-synthesized): progress, not debt
    checklist: str = ""       # what M1 must do to eliminate this debt


@dataclass
class Scorecard:
    subject: str
    categories: list[DebtCategory] = field(default_factory=list)

    @property
    def open_debt(self) -> int:
        return sum(c.count for c in self.categories if not c.automated)

    @property
    def retired(self) -> int:
        return sum(c.count for c in self.categories if c.automated)

    def by_workstream(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in self.categories:
            if not c.automated:
                out[c.workstream] = out.get(c.workstream, 0) + c.count
        return dict(sorted(out.items()))

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "open_debt": self.open_debt,
            "retired": self.retired,
            "by_workstream": self.by_workstream(),
            "categories": [c.__dict__ for c in self.categories],
        }


def _count_fns_in_rust(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        try:
            total += len(_FN_RE.findall(p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return total


_TEST_CUT_RE = re.compile(r"#\[cfg\(test\)\]|\nmod tests\b")
_FN_NAME_RE = re.compile(
    r"^\s*(?:pub(?:\(crate\))?\s+)?(?:unsafe\s+)?fn\s+(\w+)\s*[<(]", re.MULTILINE
)


def _human_ported_functions(paths: list[Path]) -> set[str]:
    """Unique IMPLEMENTATION function names across the snapshot files.

    Excludes `#[cfg(test)]` modules and `test_*` fns (a test is not a translated
    body), and dedups across the overlapping hardport/wip/verified snapshot dirs
    (the same fn is backed up in several places). This is the honest count of
    distinct human-ported bodies — the earlier per-file total double-counted
    tests and duplicate snapshots.
    """
    fns: set[str] = set()
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _TEST_CUT_RE.search(text)
        body = text[: m.start()] if m else text
        for name in _FN_NAME_RE.findall(body):
            if not name.startswith("test_"):
                fns.add(name)
    return fns


def _count_shim_runners(shim_dir: Path) -> tuple[int, int]:
    """Return (distinct shim fns, files scanned)."""
    names: set[str] = set()
    files = 0
    if not shim_dir.exists():
        return 0, 0
    for c in shim_dir.rglob("*.c"):
        files += 1
        try:
            text = c.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _SHIM_RE.finditer(text):
            names.add(m.group(1))
    return len(names), files


def _registry_len(name: str) -> int:
    try:
        from alchemist.architect import type_unifier as tu
    except Exception:
        return 0
    val = getattr(tu, name, ())
    try:
        return len(val)
    except TypeError:
        return 0


def _catalog_size() -> int:
    try:
        from alchemist.catalog import IDIOMS
        return len(IDIOMS)
    except Exception:
        return 0


def build_scorecard(repo_root: Path | None = None, subject: str = "zlib") -> Scorecard:
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    impls = root / "alchemist" / "references" / "impls"
    shims = root / "alchemist" / "references" / "shims" / subject

    # --- WS1: hand-written oracle glue (shim runners) ---
    n_shims_total, _ = _count_shim_runners(shims)
    from alchemist.autonomy.ledger import Ledger as _L
    _lg = _L.load()
    n_shims_retired = sum(1 for v in _lg.retired.values() if v.get("crate") == "shim-accessor")
    n_shims = max(0, n_shims_total - n_shims_retired)

    # --- WS3/WS4: human-ported Rust bodies (hardports, wip, verified snapshots) ---
    hardport_rs: list[Path] = []
    if impls.exists():
        for d in impls.iterdir():
            if d.is_dir() and re.search(subject, d.name, re.IGNORECASE) and (
                "hardport" in d.name or "wip" in d.name or "verified" in d.name
            ):
                hardport_rs.extend(d.rglob("*.rs"))
    n_hardport_files = len(hardport_rs)
    # Honest debt: unique IMPLEMENTATION functions (tests excluded, snapshots
    # deduped), minus those the retirement ledger proves autonomously reproducible.
    ported_fns = _human_ported_functions(hardport_rs)
    from alchemist.autonomy.ledger import Ledger
    ledger = Ledger.load()
    retired = {f for f in ported_fns if f in ledger.retired_fns()}
    n_open_bodies = len(ported_fns - retired)
    n_retired_bodies = len(retired)

    # --- WS3: curated reference impls (JSON) ---
    n_refs = 0
    if impls.exists():
        n_refs = sum(
            1
            for j in impls.glob("*.json")
            if subject.lower() in j.read_text(encoding="utf-8", errors="replace").lower()
        )

    # --- WS2: hand-specified type model (canonicals + overrides + additions) ---
    n_canon = _registry_len("DEFAULT_CANONICAL")
    n_fo = _registry_len("DEFAULT_FIELD_OVERRIDES")
    n_po = _registry_len("DEFAULT_PARAM_OVERRIDES")
    n_fa = _registry_len("DEFAULT_FIELD_ADDITIONS")
    n_types = n_canon + n_fo + n_po + n_fa

    # --- WS6: idiom catalog — RETIRED debt (now auto-detected/injected) ---
    n_idioms = _catalog_size()

    sc = Scorecard(subject=subject)
    sc.categories = [
        DebtCategory(
            key="oracle_shims", workstream="WS1",
            title="Hand-written oracle shim runners (still human-authored)",
            count=n_shims, unit="shims",
            detail=f"C glue that runs the reference + captures effect footprint. "
                   f"{n_shims_retired} of {n_shims_total} auto-synthesized + compile-validated "
                   f"by the shim generator (mechanical field accessors + call-through runners); "
                   f"the rest are custom setup/marshalling.",
            checklist="Extend the generator to the custom runners; effect-footprint inference "
                      "for full signature-driven harness gen.",
        ),
        DebtCategory(
            key="hardported_bodies", workstream="WS3/WS4",
            title="Human-ported Rust function bodies (unique, tests excluded)",
            count=n_open_bodies, unit="fns",
            detail=f"Distinct implementation functions across {n_hardport_files} snapshot "
                   f"files still needing a human port. Deduped across hardport/wip/verified "
                   f"dirs and excluding test fns (the earlier per-file count double-counted "
                   f"both). {n_retired_bodies} already retired by the WS4 regen loop.",
            checklist="Model produces + the WS4 diagnose-and-repair loop fixes these with no "
                      "human hand-porting or diagnosis. This is the core M1 debt.",
        ),
        DebtCategory(
            key="regen_retired", workstream="WS4",
            title="Functions proven autonomously reproducible (regen loop)",
            count=n_retired_bodies, unit="fns",
            detail="Body stubbed -> model refilled from the C reference -> differential tests "
                   "green, no human. Recorded in the retirement ledger with proof metadata.",
            automated=True,
            checklist="(in progress) Drive the open human-ported count down by regenerating "
                      "each function autonomously.",
        ),
        DebtCategory(
            key="curated_refs", workstream="WS3",
            title="Curated reference implementations",
            count=n_refs, unit="refs",
            detail="Known-good Rust snippets a human supplied/blessed for injection.",
            checklist="Synthesize per-function references from C automatically (probe already "
                      "does this when it can — make it the default, not the fallback).",
        ),
        DebtCategory(
            key="type_overrides", workstream="WS2",
            title="Hand-specified type-model overrides",
            count=n_types, unit="overrides",
            detail=f"{n_canon} canonical types, {n_fo} field overrides, {n_po} param overrides, "
                   f"{n_fa} field additions — the coherent model a human pinned down.",
            checklist="Infer the coherent type + ownership model from the C struct graph + usage "
                      "(aliasing detection, buffer model, ownership graph, union handling).",
        ),
        DebtCategory(
            key="idiom_catalog", workstream="WS6",
            title="C-idiom patterns (auto-detected + injected)",
            count=n_idioms, unit="idioms",
            detail="Seeded from zlib; matched by C-signal and injected per function. RETIRED: "
                   "no longer a per-run human step.",
            automated=True,
            checklist="(done) Grow the catalog as new libraries add idioms.",
        ),
    ]
    return sc


def render_scorecard(sc: Scorecard) -> str:
    lines: list[str] = []
    lines.append(f"# M1 autonomy scorecard - subject: {sc.subject}")
    lines.append("")
    lines.append(f"**Open autonomy debt: {sc.open_debt} human-supplied artifacts** "
                 f"(retired so far: {sc.retired}).")
    lines.append("")
    lines.append("Every open item is a crutch M1 (push-button zlib) must remove by "
                 "auto-synthesizing the equivalent. Byte-exact-or-refused stays sacred.")
    lines.append("")
    ws = sc.by_workstream()
    lines.append("## Debt by workstream")
    lines.append("")
    lines.append("| Workstream | Open debt |")
    lines.append("|---|---:|")
    for k, v in ws.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Categories")
    lines.append("")
    for c in sc.categories:
        status = "[RETIRED]" if c.automated else "[OPEN]"
        lines.append(f"### [{c.workstream}] {c.title} - {c.count} {c.unit}  ({status})")
        lines.append(f"- {c.detail}")
        lines.append(f"- **M1 action:** {c.checklist}")
        lines.append("")
    lines.append("---")
    lines.append("_Generated by `alchemist.autonomy.scorecard`. Re-run after each autonomy "
                 "change; the open-debt number should trend to zero for M1._")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="M1 autonomy scorecard")
    ap.add_argument("--subject", default="zlib")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)

    sc = build_scorecard(repo_root=args.repo_root, subject=args.subject)
    if args.json:
        print(json.dumps(sc.to_dict(), indent=2))
    else:
        print(render_scorecard(sc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
