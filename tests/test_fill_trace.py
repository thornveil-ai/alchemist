"""P0.1 — env-gated per-iteration fill trace.

Root-causing a fill (P0.2) previously required hand-instrumenting tdd_generator
three separate times this session. ALCHEMIST_FILL_TRACE makes it first-class:
set it to a directory and every iteration's model Rust / compile error / test
divergence lands as a file. These tests lock in that behavior.
"""

from __future__ import annotations

import os
from pathlib import Path

from alchemist.implementer.tdd_generator import TDDGenerator
from alchemist.extractor.schemas import AlgorithmSpec


def _gen():
    # The helper touches neither __init__ nor the LLM.
    return TDDGenerator.__new__(TDDGenerator)


def _alg():
    return AlgorithmSpec(name="adler32", display_name="adler32",
                         category="checksum", description="")


def test_trace_writes_when_env_set(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCHEMIST_FILL_TRACE", str(tmp_path))
    g = _gen()
    g._trace_fill(_alg(), "tinychk-checksums", "tinychk", 3, "rust", "pub fn adler32(){}")
    g._trace_fill(_alg(), "tinychk-checksums", "tinychk", 3, "compile", "E0308: mismatched types")
    g._trace_fill(_alg(), "tinychk-checksums", "tinychk", 3, "test", "DIVERGENCE: line 1")
    base = tmp_path / "tinychk-checksums__tinychk__adler32"
    assert (base / "iter03.rust").read_text() == "pub fn adler32(){}"
    assert "E0308" in (base / "iter03.compile").read_text()
    assert "DIVERGENCE" in (base / "iter03.test").read_text()


def test_trace_noop_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("ALCHEMIST_FILL_TRACE", raising=False)
    g = _gen()
    # Must not raise and must not create anything.
    g._trace_fill(_alg(), "c", "m", 1, "rust", "x")
    assert list(tmp_path.iterdir()) == []


def test_trace_never_raises_on_bad_path(tmp_path, monkeypatch):
    # A path that can't be a directory (it's under an existing file) must be
    # swallowed — tracing is diagnostic, never allowed to break a real run.
    afile = tmp_path / "afile"
    afile.write_text("x")
    monkeypatch.setenv("ALCHEMIST_FILL_TRACE", str(afile / "under-a-file"))
    _gen()._trace_fill(_alg(), "c", "m", 1, "rust", "x")  # no exception
