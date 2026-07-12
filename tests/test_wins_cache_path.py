"""P0.4 — the wins cache must anchor to the SUBJECT, not to workspace_dir.parent.

The old anchor (workspace_dir.parent/"wins") pointed at the shared temp ROOT
when translate was given an external --output, so wins were keyed only by
crate/module/fn — non-deterministic across --output locations and shared across
subjects. Anchoring to the source root makes restore deterministic regardless of
where --output sits, and lets a benchmark's per-subject clean produce a cold run.
"""

from __future__ import annotations

from pathlib import Path

from alchemist.implementer.tdd_generator import TDDGenerator


def _gen():
    # llm=None constructs a real client object but never calls it here.
    return TDDGenerator()


def test_wins_path_anchors_to_source_root(tmp_path):
    gen = _gen()
    subject = tmp_path / "subjects" / "crc32b"
    gen._source_root = subject
    # Two totally different --output locations...
    p1 = gen._wins_cache_path(Path("/tmp/leafbench_crc32b_aaa"), "c-core", "m", "crc32b")
    p2 = gen._wins_cache_path(tmp_path / "some" / "other" / "out", "c-core", "m", "crc32b")
    # ...must resolve to the SAME subject-anchored path (deterministic).
    expected = subject / ".alchemist" / "wins" / "c-core" / "m" / "crc32b.rs"
    assert p1 == expected
    assert p2 == expected


def test_wins_path_is_per_subject(tmp_path):
    gen = _gen()
    gen._source_root = tmp_path / "a"
    pa = gen._wins_cache_path(Path("/tmp/x"), "core", "m", "f")
    gen._source_root = tmp_path / "b"
    pb = gen._wins_cache_path(Path("/tmp/x"), "core", "m", "f")
    # Different subjects with the same crate/module/fn must NOT collide.
    assert pa != pb


def test_wins_path_fallback_without_source_root():
    gen = _gen()
    gen._source_root = None
    # Legacy: workspace_dir=subject/.alchemist/output -> .parent = subject/.alchemist,
    # so the fallback still lands at subject/.alchemist/wins.
    ws = Path("/proj/subj/.alchemist/output")
    p = gen._wins_cache_path(ws, "core", "m", "f")
    assert p == Path("/proj/subj/.alchemist") / "wins" / "core" / "m" / "f.rs"
