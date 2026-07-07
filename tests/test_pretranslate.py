"""Mechanical pre-translation — deterministic C scaffolding -> Rust."""

from alchemist.autonomy.pretranslate import mechanical_pretranslate, pretranslate_hint


def test_canonical_loop_becomes_range():
    out = mechanical_pretranslate("for (unsigned long i = 0; i < n; i++) s = s * 31u + d[i];")
    assert "for i in 0..(n as usize)" in out
    assert "d[i as usize]" in out                 # index cast added


def test_preincrement_loop_form():
    out = mechanical_pretranslate("for (int k = 0; k < len; ++k) acc ^= buf[k];")
    assert "for k in 0..(len as usize)" in out and "buf[k as usize]" in out


def test_hint_empty_when_nothing_mechanical():
    # a body with no canonical loop / indexing -> no hint (don't nag the model)
    assert pretranslate_hint("return x * 31 + y;") == ""


def test_hint_present_when_rewrite_applies():
    hint = pretranslate_hint("for (unsigned i = 0; i < n; i++) out[i] = in[i];")
    assert "Mechanical skeleton" in hint and "0..(n as usize)" in hint
