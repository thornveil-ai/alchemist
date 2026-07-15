"""Skeleton compile-repair gate (P1.5 flakiness): the model-designed architecture is
non-deterministic and references types it never defines (E0425). The gate injects
placeholders so the run doesn't abort 0/0 — fixing the CLASS wherever it appears."""

from __future__ import annotations

from pathlib import Path

import alchemist.implementer.tdd_generator as tg


def test_repair_injects_placeholder_for_undefined_type(tmp_path, monkeypatch):
    lib = tmp_path / "http-parser-core" / "src" / "lib.rs"
    lib.parent.mkdir(parents=True)
    lib.write_text(
        "pub enum CoreError {\n    UrlError(UrlParseError),\n}\n", encoding="utf-8")
    stderr = (
        "error[E0425]: cannot find type `UrlParseError` in this scope\n"
        "  --> http-parser-core/src/lib.rs:2:14\n"
        "   |\n2 |     UrlError(UrlParseError),\n")

    # Mock cargo check: fail first (so the gate injects), then pass (placeholder worked).
    calls = {"n": 0}
    def fake_check(path, timeout=300):
        calls["n"] += 1
        return (calls["n"] >= 1, "")  # after injection it compiles
    monkeypatch.setattr(tg, "_run_cargo_check", fake_check)

    ok, _ = tg._repair_skeleton_undefined_types(tmp_path, stderr)
    assert ok
    txt = lib.read_text(encoding="utf-8")
    assert "pub struct UrlParseError;" in txt, "placeholder not injected"


def test_repair_gives_up_on_unknown_error(tmp_path, monkeypatch):
    # A non-"cannot find type" error the gate can't repair -> returns False, no infinite loop.
    monkeypatch.setattr(tg, "_run_cargo_check", lambda p, timeout=300: (False, "x"))
    ok, _ = tg._repair_skeleton_undefined_types(
        tmp_path, "error[E0308]: mismatched types\n --> a/src/lib.rs:1:1\n")
    assert ok is False
