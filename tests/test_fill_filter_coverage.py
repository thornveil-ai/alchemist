"""The fill loop runs `cargo test <filters>` where filters come from
`_test_filters_for_fn`. If an emitted test's name suffix isn't in that filter
set, cargo runs 0 tests for the function and the fill loop FALSELY reports "no
test vectors" — refusing a function the gate-5 differential actually proves
correct. This silently inflated the refusal metric for every stateful-sequence
subject (rc4 keystream, bump_alloc op, FNV hash update/final).

The guardrail test scans test_generator.py for every emitted `test_<fn>_<suffix>`
name and asserts the filter covers it, so a new emitter can't reintroduce the bug."""

from __future__ import annotations

import re
from pathlib import Path

import alchemist.implementer.test_generator as tg_mod
from alchemist.implementer.tdd_generator import _test_filters_for_fn


def test_sequence_and_mutator_suffixes_are_filtered():
    filters = _test_filters_for_fn("foo")
    for suffix in ("seq", "aseq", "ainit", "hinit", "hupd", "hfin", "mut",
                   "state", "body", "str"):
        assert f"test_foo_{suffix}_" in filters, f"missing filter for _{suffix}_"


def test_every_emitted_test_suffix_has_a_filter():
    """Scan the emitters for `test_{fn_name}_<suffix>` and require each to be a
    prefix of some filter — a new emitter without a matching filter fails here."""
    src = Path(tg_mod.__file__).read_text(encoding="utf-8")
    suffixes = set(re.findall(r'fn test_\{fn_name\}_([a-z]+)', src))
    # catalog-style tests use `test_<fn>_vec_<name>` (emitted from other helpers)
    suffixes |= {"vec", "spec", "observer", "xform", "roundtrip"}
    filters = _test_filters_for_fn("foo")
    filterset = {f for f in filters}
    for suf in suffixes:
        assert any(f == f"test_foo_{suf}_" for f in filterset), \
            f"emitted test suffix '_{suf}_' has no fill-loop filter (would false-refuse)"


def test_smoke_filter_present():
    assert "smoke_foo" in _test_filters_for_fn("foo")
