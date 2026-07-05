"""Tests for the M1 autonomy scorecard (docs/PATH_TO_AUTONOMY.md).

Guards the inventory logic and the accounting invariants. The absolute counts
will drift as autonomy debt is paid down — that's the point — so these assert
structure and monotone properties, not fixed totals.
"""

from alchemist.autonomy import build_scorecard, render_scorecard
from alchemist.autonomy.scorecard import Scorecard, DebtCategory


def test_scorecard_builds_for_zlib():
    sc = build_scorecard(subject="zlib")
    assert isinstance(sc, Scorecard)
    assert sc.subject == "zlib"
    # zlib currently has real debt across the expected workstreams
    ws = sc.by_workstream()
    assert "WS1" in ws  # oracle shims
    assert any(k.startswith("WS3") for k in ws)  # hardported bodies
    assert sc.open_debt > 0


def test_open_debt_excludes_retired_and_totals_correctly():
    sc = build_scorecard(subject="zlib")
    open_from_cats = sum(c.count for c in sc.categories if not c.automated)
    retired_from_cats = sum(c.count for c in sc.categories if c.automated)
    assert sc.open_debt == open_from_cats
    assert sc.retired == retired_from_cats
    # by_workstream sums to open_debt (retired excluded)
    assert sum(sc.by_workstream().values()) == sc.open_debt


def test_idiom_catalog_counted_as_retired():
    sc = build_scorecard(subject="zlib")
    idiom = next((c for c in sc.categories if c.key == "idiom_catalog"), None)
    assert idiom is not None
    assert idiom.automated is True  # WS6 is done -> retired, not open debt
    assert idiom.count >= 10


def test_every_category_has_a_checklist_action():
    sc = build_scorecard(subject="zlib")
    for c in sc.categories:
        assert c.checklist, f"{c.key} missing an M1 action"
        assert c.workstream.startswith("WS")


def test_unknown_subject_yields_zero_debt_not_crash():
    sc = build_scorecard(subject="no_such_lib_xyz")
    # type overrides + idiom catalog are subject-agnostic globals, but the
    # subject-specific categories (shims, hardports, refs) should be empty.
    keys = {c.key: c.count for c in sc.categories}
    assert keys["oracle_shims"] == 0
    assert keys["hardported_bodies"] == 0
    assert keys["curated_refs"] == 0


def test_render_is_nonempty_markdown():
    sc = build_scorecard(subject="zlib")
    md = render_scorecard(sc)
    assert md.startswith("# M1 autonomy scorecard")
    assert "Debt by workstream" in md
    assert "M1 action" in md


def test_to_dict_roundtrip_shape():
    sc = build_scorecard(subject="zlib")
    d = sc.to_dict()
    assert d["subject"] == "zlib"
    assert d["open_debt"] == sc.open_debt
    assert isinstance(d["categories"], list) and d["categories"]
