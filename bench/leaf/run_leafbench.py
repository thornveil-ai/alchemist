#!/usr/bin/env python3
"""P0.11 — leaf-function benchmark runner.

Translates every subject under `bench/leaf/subjects/` and aggregates the
per-run refusal ledgers (P0.7) into one scorecard: the honest, repeatable
measure of the converter's reach on unseen pure C leaf functions.

Reports:
  - verified rate      (functions verified / total)
  - first-pass rate     (verified on iteration 1 / total)
  - refusal rate        (the north-star metric; refused / total)
  - per-category and per-function breakdown with refusal reasons

Runs where a model + gcc + cargo are available (the box). Point it at the
model with ALCHEMIST_ENDPOINT, e.g.:

    ALCHEMIST_ENDPOINT=http://localhost:8086/v1 \
      .venv/bin/python bench/leaf/run_leafbench.py

Writes bench/leaf/scorecard.json and prints a markdown summary.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBJECTS = HERE / "subjects"
SCORECARD = HERE / "scorecard.json"


def _category_of(subject: Path) -> str:
    for c in subject.glob("*.c"):
        head = c.read_text(encoding="utf-8", errors="replace")[:200]
        if "category:" in head:
            return head.split("category:", 1)[1].split(")", 1)[0].strip()
    return "?"


def _clean_state(subject: Path) -> None:
    a = subject / ".alchemist"
    for sub in ("wins", "output", "cvec"):
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


def run_subject(subject: Path, *, timeout: int = 600) -> dict:
    """Translate one subject; return its scorecard entry from the refusal ledger."""
    _clean_state(subject)
    out_dir = Path(tempfile.mkdtemp(prefix=f"leafbench_{subject.name}_"))
    entry: dict = {"subject": subject.name, "category": _category_of(subject)}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alchemist.cli", "translate",
             str(subject), "--output", str(out_dir)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(HERE.parent.parent),  # repo root
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        entry["overall"] = "PASS" if "OVERALL: PASS" in out else "FAIL"
    except subprocess.TimeoutExpired:
        entry["overall"] = "TIMEOUT"
    except Exception as e:  # noqa: BLE001
        entry["overall"] = f"ERROR: {e}"
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    ledger_path = subject / ".alchemist" / "refusal_ledger.json"
    if ledger_path.exists():
        try:
            led = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            led = {}
        fns = led.get("functions") or []
        entry["total"] = led.get("total_functions", len(fns))
        entry["verified"] = led.get("verified", 0)
        entry["refused"] = led.get("refused", 0)
        entry["refusal_rate"] = led.get("refusal_rate", 0.0)
        # first-pass = verified with <=1 repair iteration. iterations==0 is the
        # BEST case (win restored / no fill retry) — guard against the `0 or 99`
        # falsy trap that would misscore a perfect iteration-0 result as a miss.
        def _iters(f):
            it = f.get("iterations")
            return 99 if it is None else it
        entry["first_pass"] = sum(
            1 for f in fns if f.get("verified") and _iters(f) <= 1)
        entry["functions"] = [
            {"name": f.get("name"), "verified": f.get("verified"),
             "iterations": f.get("iterations"),
             "reason": (f.get("reason") or "")[:120]}
            for f in fns
        ]
    else:
        entry.update(total=0, verified=0, refused=0, refusal_rate=1.0,
                     first_pass=0, functions=[])
    return entry


def main() -> int:
    subjects = sorted(p for p in SUBJECTS.iterdir() if p.is_dir()) if SUBJECTS.exists() else []
    if not subjects:
        print(f"no subjects under {SUBJECTS}; run gen_corpus.py first")
        return 1

    results = []
    for i, subj in enumerate(subjects, 1):
        print(f"[{i}/{len(subjects)}] {subj.name} ...", flush=True)
        e = run_subject(subj)
        results.append(e)
        print(f"    {e['overall']} · verified {e.get('verified', 0)}/{e.get('total', 0)}"
              f" · first-pass {e.get('first_pass', 0)}", flush=True)

    total = sum(e.get("total", 0) for e in results)
    verified = sum(e.get("verified", 0) for e in results)
    first_pass = sum(e.get("first_pass", 0) for e in results)
    refused = total - verified
    subj_pass = sum(1 for e in results if e.get("overall") == "PASS")

    # per-category
    cats: dict[str, dict] = {}
    for e in results:
        c = cats.setdefault(e["category"], {"total": 0, "verified": 0, "first_pass": 0})
        c["total"] += e.get("total", 0)
        c["verified"] += e.get("verified", 0)
        c["first_pass"] += e.get("first_pass", 0)

    scorecard = {
        "subjects": len(subjects),
        "subjects_overall_pass": subj_pass,
        "total_functions": total,
        "verified": verified,
        "refused": refused,
        "verified_rate": round(verified / total, 4) if total else 0.0,
        "first_pass_rate": round(first_pass / total, 4) if total else 0.0,
        "refusal_rate": round(refused / total, 4) if total else 0.0,
        "by_category": cats,
        "results": results,
    }
    SCORECARD.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")

    def pct(x):
        return f"{x * 100:.1f}%"

    print("\n" + "=" * 60)
    print("LEAF BENCHMARK SCORECARD")
    print("=" * 60)
    print(f"subjects:            {len(subjects)}  ({subj_pass} OVERALL PASS)")
    print(f"functions:           {total}")
    print(f"verified:            {verified}  ({pct(scorecard['verified_rate'])})")
    print(f"first-pass (iter 1): {first_pass}  ({pct(scorecard['first_pass_rate'])})")
    print(f"refused:             {refused}  (refusal rate {pct(scorecard['refusal_rate'])})")
    print("\nby category:")
    for c, v in sorted(cats.items()):
        vr = pct(v["verified"] / v["total"]) if v["total"] else "-"
        print(f"  {c:10} {v['verified']}/{v['total']} verified ({vr})")
    print(f"\nscorecard → {SCORECARD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
