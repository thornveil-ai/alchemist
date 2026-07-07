"""Pillar 5 — verified-preserving idiomaticity: the differential gate.

The end-to-end (idiomatic iterator refactor kept, *37 breaking refactor reverted,
via cargo test) is proven on the box; here we lock the keep/revert gate.
"""

import tempfile
from pathlib import Path

from alchemist.autonomy.idiomaticity import verified_refactor, idiomatic_pass


def _mod(text):
    f = Path(tempfile.mkdtemp()) / "lib.rs"
    f.write_text(text)
    return f


def test_keeps_refactor_that_verifies():
    f = _mod("original")
    assert verified_refactor(f, "idiomatic", lambda: True) is True
    assert f.read_text() == "idiomatic"          # kept


def test_reverts_refactor_that_diverges():
    f = _mod("original")
    assert verified_refactor(f, "broken", lambda: False) is False
    assert f.read_text() == "original"           # guarantee preserved


def test_idiomatic_pass_keeps_only_verified():
    f = _mod("v0")
    # accept refactors that contain "ok", reject others
    kept = idiomatic_pass(f, ["ok-1", "bad", "ok-2"], lambda: "ok" in f.read_text())
    assert kept == 2
    assert f.read_text() == "ok-2"               # last accepted becomes baseline
