"""P0.7 — the refusal ledger (the north-star metric, made measurable)."""

from __future__ import annotations

import json
from pathlib import Path

from alchemist.reporter.refusal_ledger import build_refusal_ledger, write_refusal_ledger


class _Attempt:
    def __init__(self, name, ok, iters=1, hol=False, dec=False, err="",
                 elapsed_s=0.0, llm_calls=0, output_tokens=0, won_via=""):
        self.algorithm = name; self.crate = "c"; self.module = "m"
        self.tests_passed = ok; self.iterations = iters
        self.escalated_to_holistic = hol; self.escalated_to_decomposition = dec
        self.last_error = err
        self.elapsed_s = elapsed_s; self.llm_calls = llm_calls
        self.output_tokens = output_tokens; self.won_via = won_via


class _Result:
    def __init__(self, attempts):
        self.attempts = attempts


def test_ledger_counts_and_rate():
    r = _Result([
        _Attempt("adler32", True, 1),
        _Attempt("crc32", True, 1),
        _Attempt("hardfn", False, 5, hol=True, err="no test vectors"),
    ])
    led = build_refusal_ledger(r, "tinychk")
    assert led["subject"] == "tinychk"
    assert led["total_functions"] == 3
    assert led["verified"] == 2
    assert led["refused"] == 1
    assert led["refusal_rate"] == round(1 / 3, 4)
    hard = next(f for f in led["functions"] if f["name"] == "hardfn")
    assert hard["verified"] is False
    assert "no test vectors" in hard["reason"]
    assert hard["escalated_holistic"] is True
    good = next(f for f in led["functions"] if f["name"] == "adler32")
    assert good["verified"] is True and good["reason"] is None


def test_ledger_telemetry_rollup():
    """P0.14: per-function timing/cost + a subject roll-up (total spend, slowest,
    costliest) so a ledger scan shows where the budget went."""
    r = _Result([
        _Attempt("cheap", True, 1, elapsed_s=2.0, llm_calls=1, output_tokens=300),
        _Attempt("cached", True, 0, elapsed_s=0.5, llm_calls=0, output_tokens=0),
        _Attempt("expensive", True, 4, elapsed_s=41.0, llm_calls=6, output_tokens=9000),
    ])
    led = build_refusal_ledger(r, "s")
    t = led["telemetry"]
    assert t["total_elapsed_s"] == 43.5
    assert t["total_llm_calls"] == 7
    assert t["total_output_tokens"] == 9300
    assert t["slowest_fn"] == "expensive" and t["slowest_fn_elapsed_s"] == 41.0
    assert t["costliest_fn"] == "expensive" and t["costliest_fn_output_tokens"] == 9000
    # a cached-win restore is visible as elapsed>0 but zero model spend
    cached = next(f for f in led["functions"] if f["name"] == "cached")
    assert cached["llm_calls"] == 0 and cached["elapsed_s"] == 0.5


def test_ledger_wins_by_tier():
    """P0.6: each verified fn is attributed to the escalation tier that won it,
    and the roll-up counts wins per tier (a refused fn contributes to no tier)."""
    r = _Result([
        _Attempt("a", True, won_via="cached"),
        _Attempt("b", True, won_via="single"),
        _Attempt("c", True, won_via="single"),
        _Attempt("d", True, won_via="multi_sample"),
        _Attempt("e", True, won_via="holistic", hol=True),
        _Attempt("f", True, won_via="decomposition", dec=True),
        _Attempt("g", False, err="refused"),   # no tier
    ])
    led = build_refusal_ledger(r, "s")
    wt = led["wins_by_tier"]
    assert wt == {"cached": 1, "template": 0, "single": 2,
                  "multi_sample": 1, "holistic": 1, "decomposition": 1}
    assert sum(wt.values()) == led["verified"]  # every verified fn attributed
    b = next(f for f in led["functions"] if f["name"] == "b")
    assert b["won_via"] == "single"
    g = next(f for f in led["functions"] if f["name"] == "g")
    assert g["won_via"] == ""  # refused fns carry no tier


def test_ledger_all_verified_zero_rate():
    r = _Result([_Attempt("a", True), _Attempt("b", True)])
    led = build_refusal_ledger(r, "s")
    assert led["refused"] == 0 and led["refusal_rate"] == 0.0


def test_ledger_empty_is_safe():
    led = build_refusal_ledger(_Result([]), "s")
    assert led["total_functions"] == 0 and led["refusal_rate"] == 0.0


def test_write_persists_json(tmp_path):
    r = _Result([_Attempt("a", True), _Attempt("b", False, 5, err="boom")])
    led, path = write_refusal_ledger(r, tmp_path / ".alchemist", "s")
    assert path is not None
    on_disk = json.loads(Path(path).read_text())
    assert on_disk["refused"] == 1
    assert on_disk["functions"][1]["reason"] == "boom"


def test_write_never_raises_on_bad_dir(tmp_path):
    afile = tmp_path / "afile"; afile.write_text("x")
    led, path = write_refusal_ledger(_Result([_Attempt("a", True)]), afile / "under-file", "s")
    # Build still returns a ledger; write fails gracefully to None.
    assert led["verified"] == 1 and path is None
