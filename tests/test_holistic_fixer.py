"""P0.5 — the holistic fixer must not silently burn its iteration budget.

Two failure modes it used to hit: an empty patch (or an all-rejected patch)
just `continue`d, and a patch that rewrote a file to byte-identical content
was counted as a "change" — both let the loop grind every iteration with no
progress and no diagnosis. Now it detects real no-ops, bails after two in a
row with a `bail_reason`, and only counts genuine content changes.
"""

from __future__ import annotations

import alchemist.implementer.holistic as H
from alchemist.implementer.holistic import HolisticFixer


class _Resp:
    def __init__(self, structured):
        self.structured = structured
        self.content = ""


class _FakeLLM:
    """Returns a scripted sequence of structured responses."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def create_cached_context(self, *a, **k):
        return None

    def call_structured(self, *a, **k):
        self.calls += 1
        r = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        return _Resp(r)


def _crate(tmp_path):
    d = tmp_path / "crate"
    (d / "src").mkdir(parents=True)
    (d / "Cargo.toml").write_text(
        '[package]\nname="c"\nversion="0.1.0"\nedition="2021"\n', encoding="utf-8")
    (d / "src" / "lib.rs").write_text("pub fn f() -> i32 { 0 }\n", encoding="utf-8")
    return d


def test_empty_patch_bails_after_two_iters(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "cargo_check", lambda *a, **k: (False, "error[E0308]: boom"))
    fixer = HolisticFixer(llm=_FakeLLM([{"files": {}}]), max_iter=5)
    res = fixer.fix_crate(_crate(tmp_path))
    assert res.iterations_run == 2, "must bail after 2 consecutive empty patches, not grind to 5"
    assert res.bail_reason and "no-op" in res.bail_reason
    assert res.files_changed == []
    assert not res.success


def test_identical_content_is_not_a_change(tmp_path, monkeypatch):
    monkeypatch.setattr(H, "cargo_check", lambda *a, **k: (False, "error: still broken"))
    d = _crate(tmp_path)
    same = (d / "src" / "lib.rs").read_text(encoding="utf-8")
    # The model keeps returning the file exactly as-is — a no-op patch.
    fixer = HolisticFixer(llm=_FakeLLM([{"files": {"src/lib.rs": same}}]),
                          max_iter=5, reject_stubs=False)
    res = fixer.fix_crate(d)
    assert res.files_changed == [], "byte-identical rewrite must not count as a change"
    assert res.iterations_run == 2 and res.bail_reason


def test_real_fix_succeeds_without_bail(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_check(*a, **k):
        calls["n"] += 1
        return (calls["n"] >= 2, "" if calls["n"] >= 2 else "error: broken")

    monkeypatch.setattr(H, "cargo_check", fake_check)
    d = _crate(tmp_path)
    fixer = HolisticFixer(
        llm=_FakeLLM([{"files": {"src/lib.rs": "pub fn f() -> i32 { 42 }\n"}}]),
        max_iter=5, reject_stubs=False)
    res = fixer.fix_crate(d)
    assert res.success
    assert res.bail_reason == ""
    assert "src/lib.rs" in res.files_changed
    assert (d / "src" / "lib.rs").read_text().strip().endswith("{ 42 }")
