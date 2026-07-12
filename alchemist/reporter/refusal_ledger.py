"""P0.7 — the refusal ledger: the north-star metric, made measurable.

Every translate run emits a per-function record of what verified, what was
refused, and WHY. Refusal rate (refused / total) is the number we drive toward
zero — it is the honest measure of the converter's reach.

Fail-closed by design: a refused function is an HONEST refusal (nothing wrong is
ever emitted as verified). This module doesn't change that; it just makes the
count and the reasons explicit so reliability work has a metric to move.
"""

from __future__ import annotations

import json
from pathlib import Path


def build_refusal_ledger(result, subject: str = "") -> dict:
    """Summarize a TDDResult's per-function attempts into a ledger dict.

    Tolerant of any object exposing `.attempts` with FunctionAttempt-shaped
    entries; missing fields degrade gracefully.
    """
    attempts = list(getattr(result, "attempts", None) or [])
    fns: list[dict] = []
    verified = 0
    for a in attempts:
        ok = bool(getattr(a, "tests_passed", False))
        if ok:
            verified += 1
        fns.append({
            "name": getattr(a, "algorithm", ""),
            "crate": getattr(a, "crate", ""),
            "module": getattr(a, "module", ""),
            "verified": ok,
            "iterations": getattr(a, "iterations", 0),
            "escalated_holistic": bool(getattr(a, "escalated_to_holistic", False)),
            "escalated_decomposition": bool(getattr(a, "escalated_to_decomposition", False)),
            # P0.6 escalation-ladder audit: which tier produced the win.
            "won_via": (getattr(a, "won_via", "") or "") if ok else "",
            # P0.14 per-function telemetry: wall-clock + model spend.
            "elapsed_s": round(float(getattr(a, "elapsed_s", 0.0) or 0.0), 3),
            "llm_calls": int(getattr(a, "llm_calls", 0) or 0),
            "output_tokens": int(getattr(a, "output_tokens", 0) or 0),
            # A refused fn carries its last error as the reason; verified fns have none.
            "reason": None if ok else (getattr(a, "last_error", "") or "refused"),
        })
    total = len(attempts)
    refused = total - verified
    # P0.14 subject-level roll-up: total cost + the slowest / most-expensive
    # function, so a scan of the ledger surfaces where the budget went.
    total_elapsed = round(sum(f["elapsed_s"] for f in fns), 3)
    total_calls = sum(f["llm_calls"] for f in fns)
    total_tokens = sum(f["output_tokens"] for f in fns)
    slowest = max(fns, key=lambda f: f["elapsed_s"], default=None)
    costliest = max(fns, key=lambda f: f["output_tokens"], default=None)
    # P0.6 escalation-ladder audit: how many verified fns each tier won. Zero for
    # a tier over a corpus = it isn't earning its budget (dead weight or a rare
    # safety net). Ordered cheap→expensive.
    _tiers = ("cached", "template", "single", "multi_sample", "holistic", "decomposition")
    by_tier = {t: 0 for t in _tiers}
    for f in fns:
        wv = f.get("won_via") or ""
        if wv in by_tier:
            by_tier[wv] += 1
    return {
        "subject": subject,
        "total_functions": total,
        "verified": verified,
        "refused": refused,
        "refusal_rate": round(refused / total, 4) if total else 0.0,
        "telemetry": {
            "total_elapsed_s": total_elapsed,
            "total_llm_calls": total_calls,
            "total_output_tokens": total_tokens,
            "slowest_fn": slowest["name"] if slowest else None,
            "slowest_fn_elapsed_s": slowest["elapsed_s"] if slowest else 0.0,
            "costliest_fn": costliest["name"] if costliest else None,
            "costliest_fn_output_tokens": costliest["output_tokens"] if costliest else 0,
        },
        # P0.6: verified-wins-by-escalation-tier (proves each tier adds wins).
        "wins_by_tier": by_tier,
        "functions": fns,
    }


def write_refusal_ledger(result, out_dir: Path, subject: str = "") -> tuple[dict, Path | None]:
    """Build the ledger and persist it to `<out_dir>/refusal_ledger.json`.

    Returns (ledger_dict, path_or_None). Never raises — a failed write must not
    break a translate run; the ledger is diagnostic, not load-bearing.
    """
    ledger = build_refusal_ledger(result, subject)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "refusal_ledger.json"
        path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        return ledger, path
    except Exception:  # noqa: BLE001
        return ledger, None
