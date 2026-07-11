"""P0.7 — the refusal ledger (the north-star metric, made measurable)."""

from __future__ import annotations

import json
from pathlib import Path

from alchemist.reporter.refusal_ledger import build_refusal_ledger, write_refusal_ledger


class _Attempt:
    def __init__(self, name, ok, iters=1, hol=False, dec=False, err=""):
        self.algorithm = name; self.crate = "c"; self.module = "m"
        self.tests_passed = ok; self.iterations = iters
        self.escalated_to_holistic = hol; self.escalated_to_decomposition = dec
        self.last_error = err


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
