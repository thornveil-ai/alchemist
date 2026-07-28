#!/usr/bin/env python3
"""Alchemist batch engine — cruise many C subjects through the pipeline, capture
everything, and tell us exactly what bulk needs the frontier teacher.

For each subject dir (containing C sources):
  1. run `alchemist translate` (the model comes from the ambient ALCHEMIST_*
     env, so the caller picks fast-local vs reasoner vs frontier);
  2. read the per-subject refusal_ledger.json;
  3. append every VERIFIED (C fn -> Rust fn) win to corpus/pairs.jsonl
     (the zero-noise SFT corpus);
  4. append every REFUSED fn (C source + reason + telemetry) to
     corpus/escalation_queue.jsonl (the frontier work-list);
  5. accumulate a batch_report.json dashboard (per-subject + totals + reason /
     won_via / shape histograms + tokens + wall-clock + throughput).

Resumable (skips subjects already recorded in corpus/batch_done.txt), robust
(one subject failing never kills the batch), unattended.

Usage:
  python tools/batch_run.py --subjects subjects/a subjects/b ...
  python tools/batch_run.py --manifest corpus/harvest.txt   # one subject dir/line
  python tools/batch_run.py --glob 'subjects/*'             # everything with a .c
  env: ALCHEMIST_ENDPOINT etc pick the model; ALCHEMIST_BATCH_TIMEOUT_S per subject
"""
import argparse
import glob as _glob
import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/data/rigrun/projects/alchemist")
CORPUS = ROOT / "corpus"
PAIRS = CORPUS / "pairs.jsonl"
ESCAL = CORPUS / "escalation_queue.jsonl"
REPORT = CORPUS / "batch_report.json"
DONE = CORPUS / "batch_done.txt"


def _extract_c_fn(c_text: str, fn_name: str) -> str | None:
    m = re.search(
        r"(?:^|\n)[A-Za-z_][\w \t\*\(\),]*?\b" + re.escape(fn_name) + r"\s*\([^;{]*\)\s*\{",
        c_text)
    if not m:
        return None
    start = m.start() if c_text[m.start()] != "\n" else m.start() + 1
    brace = c_text.index("{", m.end() - 1)
    depth, i = 1, brace + 1
    while depth and i < len(c_text):
        if c_text[i] == "{":
            depth += 1
        elif c_text[i] == "}":
            depth -= 1
        i += 1
    return c_text[start:i]


def _c_blob(subj_dir: Path) -> str:
    return "\n".join(
        cf.read_text(encoding="utf-8", errors="replace")
        for cf in sorted(subj_dir.glob("*.c")))


def _win_bodies(subj_dir: Path) -> dict:
    """fn_name -> verified Rust body, from .alchemist/wins."""
    out = {}
    wins = subj_dir / ".alchemist" / "wins"
    if wins.exists():
        for rs in wins.glob("**/*.rs"):
            body = rs.read_text(encoding="utf-8", errors="replace").strip()
            if body and "unimplemented!" not in body:
                out[rs.stem] = body
    return out


def _load_done() -> set:
    return set(DONE.read_text().split()) if DONE.exists() else set()


def _mark_done(name: str):
    with DONE.open("a") as f:
        f.write(name + "\n")


def _classify_refusal(reason: str) -> tuple[str, str]:
    """Map a raw refusal reason -> (class, cleaned_reason). Splitting drafter_empty
    out of model_hard keeps the frontier work-list honest: 'LLM returned empty' is
    'the drafter gave up' (escalate to a stronger model), not 'attempted and wrong'.
    reason_unclear catches cargo build-progress lines that leaked into the reason
    field via an upstream capture bug, so they stop inflating model_hard."""
    rl = reason.lower().strip()
    # idempotent: recognize our own already-cleaned marker
    if "reason-capture bug" in rl:
        return "reason_unclear", "cargo output (reason-capture bug)"
    if rl.startswith(("checking ", "compiling ", "finished ", "building ",
                      "updating ", "downloading ")):
        return "reason_unclear", "cargo output (reason-capture bug)"
    if ("no verifiable test vectors" in rl or "no correctness test" in rl
            or "cannot verify" in rl or "no test vectors" in rl):
        return "oracle_gap", reason
    if "compile error" in rl or "error[e" in rl:
        # rustc error[Ennnn] / our "compile error (test harness ...)" marker: the
        # SKELETON/HARNESS produced non-compiling code (e.g. a sibling fn's return
        # type poisoned the shared test module). A harness bug to fix, NOT a model
        # or oracle gap — and the body itself may be byte-exact-correct.
        return "compile_fail", reason
    if "llm returned empty" in rl or ("empty" in rl and "llm" in rl):
        return "drafter_empty", reason
    return "model_hard", reason


def run_subject(subj: Path, timeout_s: int, collect_only: bool = False) -> dict:
    name = subj.name
    out_dir = f"/tmp/batch_out/{name}"
    t0 = time.time()
    if not collect_only:
        # Explicit env so the translate subprocess reliably gets the drafter
        # config. Default thinking OFF (Gemma-class models burn the token budget
        # "thinking" and return empty content otherwise).
        _env = os.environ.copy()
        _env.setdefault("ALCHEMIST_DISABLE_THINKING", "1")
        try:
            subprocess.run(
                [str(ROOT / ".venv/bin/python"), "-m", "alchemist.cli", "translate",
                 str(subj), "--output", out_dir],
                cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_s,
                env=_env)
        except subprocess.TimeoutExpired:
            return {"subject": name, "status": "timeout", "elapsed_s": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            return {"subject": name, "status": f"error:{e}", "elapsed_s": round(time.time() - t0, 1)}

    ledger_p = subj / ".alchemist" / "refusal_ledger.json"
    if not ledger_p.exists():
        return {"subject": name, "status": "no-ledger", "elapsed_s": round(time.time() - t0, 1)}
    ledger = json.loads(ledger_p.read_text())
    c_blob = _c_blob(subj)
    wins = _win_bodies(subj)

    verified_pairs, escalations = [], []
    reasons, tiers = {}, {}
    for fn in ledger.get("functions", []):
        nm = fn["name"]
        if fn.get("verified"):
            tiers[fn.get("won_via") or "?"] = tiers.get(fn.get("won_via") or "?", 0) + 1
            rust = wins.get(nm)
            c_fn = _extract_c_fn(c_blob, nm) if c_blob else None
            if rust and c_fn:
                verified_pairs.append({
                    "subject": name, "function": nm, "c": c_fn, "rust": rust,
                    "won_via": fn.get("won_via"), "source": "alchemist-verified-win",
                    "verified": "byte-exact-differential"})
        else:
            cls, reason = _classify_refusal(fn.get("reason") or "unknown")
            rkey = reason.split("—")[0].strip()[:40]
            reasons[rkey] = reasons.get(rkey, 0) + 1
            c_fn = _extract_c_fn(c_blob, nm) if c_blob else None
            escalations.append({
                "subject": name, "function": nm, "c": c_fn or "", "reason": reason,
                "class": cls,
                "escalated_decomposition": fn.get("escalated_decomposition", False)})

    # append corpus + escalation queue
    with PAIRS.open("a", encoding="utf-8") as f:
        for p in verified_pairs:
            f.write(json.dumps(p) + "\n")
    with ESCAL.open("a", encoding="utf-8") as f:
        for e in escalations:
            f.write(json.dumps(e) + "\n")

    tel = ledger.get("telemetry", {})
    return {
        "subject": name, "status": "ok",
        "total": ledger.get("total_functions", 0),
        "verified": ledger.get("verified", 0),
        "refused": ledger.get("refused", 0),
        "pairs_captured": len(verified_pairs),
        "escalations": len(escalations),
        "reasons": reasons, "won_via": tiers,
        "out_tokens": tel.get("total_output_tokens", 0),
        "llm_calls": tel.get("total_llm_calls", 0),
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", nargs="*", default=[])
    ap.add_argument("--manifest")
    ap.add_argument("--glob")
    ap.add_argument("--force", action="store_true", help="re-run already-done subjects")
    ap.add_argument("--collect-only", action="store_true",
                    help="skip translate; aggregate existing ledgers/wins into corpus + escalation queue")
    args = ap.parse_args()
    CORPUS.mkdir(exist_ok=True)
    timeout_s = int(os.environ.get("ALCHEMIST_BATCH_TIMEOUT_S", "5400"))

    subs = list(args.subjects)
    if args.manifest:
        subs += [ln.strip() for ln in Path(args.manifest).read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")]
    if args.glob:
        subs += [d for d in _glob.glob(args.glob) if list(Path(d).glob("*.c"))]
    subs = [Path(s) for s in dict.fromkeys(subs)]

    if args.collect_only:
        # fresh rebuild of the corpus from existing ledgers/wins
        for p in (PAIRS, ESCAL, DONE, REPORT):
            if p.exists():
                p.unlink()
    done = set() if (args.force or args.collect_only) else _load_done()
    report = json.loads(REPORT.read_text()) if REPORT.exists() else {"subjects": [], "totals": {}}

    print(f"batch: {len(subs)} subjects | timeout {timeout_s}s/subject | "
          f"model endpoint {os.environ.get('ALCHEMIST_ENDPOINT','(default)')}")
    for subj in subs:
        if subj.name in done:
            print(f"  skip {subj.name} (done)"); continue
        if not subj.exists() or not list(subj.glob("*.c")):
            print(f"  skip {subj.name} (no .c)"); continue
        print(f"  >> {subj.name} ...", flush=True)
        r = run_subject(subj, timeout_s, collect_only=args.collect_only)
        report["subjects"].append(r)
        _mark_done(subj.name)
        REPORT.write_text(json.dumps(report, indent=2))
        v = r.get("verified", 0); tot = r.get("total", 0); p = r.get("pairs_captured", 0)
        print(f"     {r['status']}: {v}/{tot} verified, +{p} pairs, "
              f"{r.get('escalations',0)} escalations, {r.get('elapsed_s',0)}s", flush=True)

    # totals
    ok = [s for s in report["subjects"] if s.get("status") == "ok"]
    tot_reasons, tot_tiers = {}, {}
    for s in ok:
        for k, n in (s.get("reasons") or {}).items():
            tot_reasons[k] = tot_reasons.get(k, 0) + n
        for k, n in (s.get("won_via") or {}).items():
            tot_tiers[k] = tot_tiers.get(k, 0) + n
    # tally escalation classes from the queue
    import collections as _collections
    _cls = _collections.Counter()
    if ESCAL.exists():
        for ln in ESCAL.read_text().splitlines():
            if not ln.strip():
                continue
            try:
                _cls[json.loads(ln).get("class") or "?"] += 1
            except Exception:  # noqa: BLE001
                continue
    model_hard = _cls.get("model_hard", 0)
    oracle_gap = _cls.get("oracle_gap", 0)
    drafter_empty = _cls.get("drafter_empty", 0)
    compile_fail = _cls.get("compile_fail", 0)
    reason_unclear = _cls.get("reason_unclear", 0)
    report["totals"] = {
        "subjects_ok": len(ok),
        "functions": sum(s.get("total", 0) for s in ok),
        "verified": sum(s.get("verified", 0) for s in ok),
        "pairs_captured": sum(s.get("pairs_captured", 0) for s in ok),
        "escalations": sum(s.get("escalations", 0) for s in ok),
        "escalations_model_hard": model_hard,   # frontier-teacher work-list (attempted, wrong)
        "escalations_drafter_empty": drafter_empty,  # drafter gave up → stronger model
        "escalations_oracle_gap": oracle_gap,   # needs a new oracle SHAPE, not a model
        "escalations_compile_fail": compile_fail,  # skeleton/harness produced non-compiling code (harness bug)
        "escalations_reason_unclear": reason_unclear,  # capture-bug noise, not a real refusal
        "out_tokens": sum(s.get("out_tokens", 0) for s in ok),
        "refusal_reason_histogram": dict(sorted(tot_reasons.items(), key=lambda x: -x[1])),
        "won_via_histogram": tot_tiers,
    }
    REPORT.write_text(json.dumps(report, indent=2))
    t = report["totals"]
    print("\n=== BATCH TOTALS ===")
    print(f"  {t['verified']}/{t['functions']} verified across {t['subjects_ok']} subjects")
    print(f"  pairs captured: {t['pairs_captured']} (-> {PAIRS})")
    print(f"  escalations: {t['escalations']}  = {t['escalations_model_hard']} MODEL-HARD "
          f"+ {t.get('escalations_drafter_empty', 0)} DRAFTER-EMPTY (→stronger model) "
          f"+ {t['escalations_oracle_gap']} ORACLE-GAP (→new shapes) "
          f"+ {t.get('escalations_compile_fail', 0)} COMPILE-FAIL (→harness bug) "
          f"+ {t.get('escalations_reason_unclear', 0)} unclear")
    print(f"  top refusal reasons: {list(t['refusal_reason_histogram'].items())[:6]}")


if __name__ == "__main__":
    main()
