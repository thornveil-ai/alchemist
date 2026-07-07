"""Item 4 — the shippable front-end: `alchemist translate <source>`.

Runs the whole pipeline over a project and writes a real deliverable to disk:
  - manifest.json   : the signed ProjectManifest attestation
  - report.md       : a human-readable per-function dashboard (verified/partial/refused)
  - workspace/      : the cargo workspace of verified crates (emitted by the pipeline)

The report is the honest face of the tool: what verified, what stayed partial, what
was refused and why -- an accreditor's one-page read.
"""

from __future__ import annotations

import json
from pathlib import Path


def _yn(v) -> str:
    return "yes" if v is True else ("no" if v is False else "-")


def render_markdown(attestation: dict) -> str:
    s = attestation["summary"]
    verified = s["by_verdict"].get("verified", 0)
    lines = [
        "# Alchemist translation report: %s" % attestation["project"],
        "",
        "**%d/%d functions verified** (%.0f%%) · signed `sha256:%s`"
        % (verified, s["total"], s["verified_fraction"] * 100, attestation["sha256"][:16]),
        "",
        "Every *verified* row is byte-exact against the compiled C on the differential "
        "oracle; *refused* rows are honestly out of scope (never a silent gap).",
        "",
        "| Function | Verdict | Memory-safe | Miri | CWEs eliminated / reason |",
        "|---|---|---|---|---|",
    ]
    order = {"verified": 0, "partial": 1, "refused": 2}
    for f in sorted(attestation["functions"], key=lambda d: (order.get(d["verdict"], 9), d["function"])):
        detail = ", ".join(f.get("cwes") or []) if f["verdict"] == "verified" else (f.get("reason") or "")
        lines.append("| `%s` | %s | %s | %s | %s |"
                     % (f["function"], f["verdict"], _yn(f.get("memory_safe")),
                        _yn(f.get("miri")), detail or "-"))
    return "\n".join(lines) + "\n"


def run_cli(argv=None) -> int:
    import argparse
    import os
    ap = argparse.ArgumentParser(prog="alchemist translate",
                                 description="Autonomously convert legacy C to verified safe Rust.")
    ap.add_argument("source", help="git URL, tarball, or local directory of C to translate")
    ap.add_argument("--out", default="alchemist-out", help="output directory")
    ap.add_argument("--miri", action="store_true", help="prove UB-free under Miri")
    ap.add_argument("--max-files", type=int, default=None)
    args = ap.parse_args(argv)

    from alchemist.config import AlchemistConfig
    from alchemist.llm.client import AlchemistLLM
    from alchemist.autonomy.pipeline import translate_project
    from alchemist.autonomy.fill_quality import PersistentExampleStore

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    llm = AlchemistLLM(AlchemistConfig())
    store = PersistentExampleStore(out / "examples.json")
    manifest = translate_project(args.source, out / "work", llm, env, miri=args.miri,
                                 max_files=args.max_files, store=store)
    att = manifest.attest()
    (out / "manifest.json").write_text(json.dumps(att, indent=1))
    (out / "report.md").write_text(render_markdown(att))
    s = att["summary"]
    print("wrote %s/manifest.json and report.md — %d/%d verified"
          % (out, s["by_verdict"].get("verified", 0), s["total"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
