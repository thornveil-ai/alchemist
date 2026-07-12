#!/usr/bin/env python3
"""P1.10 — unattended whole-library benchmark runner.

Points the converter at a curated set of real C LIBRARIES (not single leaf
functions), runs each COLD (no cached wins), and aggregates the per-library
refusal ledgers into one scorecard. This is the "walk away, collect scorecards"
harness the P1 exit criterion needs: an unseen library → a verified Rust
workspace, hands-off, at <5% refusal.

The north-star is the OVERALL function-level refusal rate across every function
in every library — that is the P1 number we drive under 5%.

Runs where a model + gcc + cargo are available (the box):

    ALCHEMIST_ENDPOINT=http://localhost:8086/v1 \
      .venv/bin/python bench/lib/run_libbench.py

Select libraries with ALCHEMIST_LIBS="base64,sha256,..." (default = the P1 set).
Writes bench/lib/scorecard.json and prints a per-library + overall summary.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SUBJECTS = REPO / "subjects"
SCORECARD = HERE / "scorecard.json"

# The P1 set: small/mid unseen C libraries that build standalone. Ordered
# roughly easy→hard. Override with ALCHEMIST_LIBS.
DEFAULT_LIBS = [
    "base64",    # 3 files — text codec
    "sha256",    # digest
    "siphash",   # keyed hash
    "murmur3",   # seeded hash family
    "rc4",       # stateful stream cipher
    "hashkit",   # small hash collection
    "heap",      # a small container / structure
    "jsmn",      # a real JSON parser (state machine)
]

# Whole libraries need a much larger budget than a single leaf function.
PER_LIB_TIMEOUT = int(os.environ.get("ALCHEMIST_LIB_TIMEOUT", "3600"))


def _clean_state(subject: Path) -> None:
    """Truly cold: drop wins, output, cvec, oracle and any run json so the
    library fills from scratch (P0.4 anchored wins to subject/.alchemist/wins)."""
    a = subject / ".alchemist"
    for sub in ("wins", "output", "cvec", "oracle"):
        shutil.rmtree(a / sub, ignore_errors=True)
    for j in a.glob("*.json"):
        try:
            j.unlink()
        except OSError:
            pass
    lock = a / "workspace.lock"
    try:
        lock.unlink()
    except OSError:
        pass


def run_library(name: str, *, timeout: int = PER_LIB_TIMEOUT) -> dict:
    subject = SUBJECTS / name
    entry: dict = {"library": name}
    if not subject.is_dir():
        entry.update(overall="MISSING", total=0, verified=0, refused=0, refusal_rate=1.0)
        return entry
    _clean_state(subject)
    out_dir = Path(tempfile.mkdtemp(prefix=f"libbench_{name}_"))
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alchemist.cli", "translate",
             str(subject), "--output", str(out_dir)],
            capture_output=True, text=True, timeout=timeout, cwd=str(REPO),
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        entry["overall"] = "PASS" if "OVERALL: PASS" in out else "FAIL"
    except subprocess.TimeoutExpired:
        entry["overall"] = "TIMEOUT"
    except Exception as e:  # noqa: BLE001
        entry["overall"] = f"ERROR: {e}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    led_path = subject / ".alchemist" / "refusal_ledger.json"
    if led_path.exists():
        try:
            led = json.loads(led_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            led = {}
        entry["total"] = led.get("total_functions", 0)
        entry["verified"] = led.get("verified", 0)
        entry["refused"] = led.get("refused", 0)
        entry["refusal_rate"] = led.get("refusal_rate", 1.0)
        entry["wins_by_tier"] = led.get("wins_by_tier", {})
        entry["telemetry"] = led.get("telemetry", {})
        # The reasons refused functions gave — the triage worklist.
        entry["refused_fns"] = [
            {"name": f.get("name"), "reason": (f.get("reason") or "")[:140]}
            for f in (led.get("functions") or []) if not f.get("verified")
        ]
    else:
        entry.update(total=0, verified=0, refused=0, refusal_rate=1.0,
                     wins_by_tier={}, telemetry={}, refused_fns=[])
    return entry


def main() -> int:
    libs = [s.strip() for s in os.environ.get("ALCHEMIST_LIBS", "").split(",") if s.strip()]
    if not libs:
        libs = DEFAULT_LIBS

    results = []
    for i, name in enumerate(libs, 1):
        print(f"[{i}/{len(libs)}] {name} ...", flush=True)
        e = run_library(name)
        results.append(e)
        print(f"    {e['overall']} · verified {e.get('verified', 0)}/{e.get('total', 0)}"
              f" · refusal {e.get('refusal_rate', 1.0) * 100:.1f}%", flush=True)

    total = sum(e.get("total", 0) for e in results)
    verified = sum(e.get("verified", 0) for e in results)
    refused = total - verified
    libs_pass = sum(1 for e in results if e.get("overall") == "PASS")

    scorecard = {
        "libraries": len(libs),
        "libraries_overall_pass": libs_pass,
        "total_functions": total,
        "verified": verified,
        "refused": refused,
        # THE P1 number: function-level refusal across every library.
        "overall_refusal_rate": round(refused / total, 4) if total else 1.0,
        "results": results,
    }
    SCORECARD.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")

    def pct(x):
        return f"{x * 100:.1f}%"

    print("\n" + "=" * 62)
    print("LIBRARY BENCHMARK SCORECARD (P1)")
    print("=" * 62)
    print(f"libraries:            {len(libs)}  ({libs_pass} OVERALL PASS)")
    print(f"functions:            {total}")
    print(f"verified:             {verified}")
    print(f"refused:              {refused}")
    print(f"OVERALL REFUSAL RATE: {pct(scorecard['overall_refusal_rate'])}   (P1 target <5%)")
    print("\nper library:")
    for e in results:
        print(f"  {e['library']:12} {e.get('overall',''):8} "
              f"{e.get('verified',0)}/{e.get('total',0)} verified · "
              f"refusal {pct(e.get('refusal_rate', 1.0))}")
    # Surface the triage worklist: every refused function + its reason.
    worklist = [(e["library"], r) for e in results for r in e.get("refused_fns", [])]
    if worklist:
        print(f"\nrefused functions ({len(worklist)}) — triage worklist:")
        for lib, r in worklist[:40]:
            print(f"  {lib}:{r['name']} — {r['reason']}")
    print(f"\nscorecard → {SCORECARD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
