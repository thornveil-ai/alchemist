"""P0.13 — deterministic replay: ALCHEMIST_DETERMINISTIC makes the fill loop
decode greedily (temp 0) and collapse the multi-sample fan-out to one sample,
so the same subject + fixed fuzz seed reproduces byte-identical Rust across runs.
"""

from __future__ import annotations

from alchemist.implementer.tdd_generator import TDDGenerator


def test_deterministic_env_collapses_sampling(monkeypatch):
    monkeypatch.setenv("ALCHEMIST_DETERMINISTIC", "1")
    gen = TDDGenerator(multi_sample_temperature=0.35, multi_sample_n=6)
    assert gen._deterministic is True
    # Greedy, single-sample: the two sources of run-to-run variance are removed.
    assert gen.multi_sample_temperature == 0.0
    assert gen.multi_sample_n == 1


def test_non_deterministic_by_default(monkeypatch):
    monkeypatch.delenv("ALCHEMIST_DETERMINISTIC", raising=False)
    gen = TDDGenerator(multi_sample_temperature=0.35, multi_sample_n=6)
    assert gen._deterministic is False
    # Sampling fan-out preserved when not in deterministic mode (finds more wins).
    assert gen.multi_sample_temperature == 0.35
    assert gen.multi_sample_n == 6
