"""Model over-escaping repair: the LLM emits Rust string/char literals with C/JSON-style
escapes like `"{}\\[\\]"` — `\\[` and `\\]` are HARD compile errors in Rust ("unknown
character escape"), and one such typo in a single function breaks the ENTIRE crate,
blocking verification of every sibling function. Observed on jsmn_parse's tokenizer
string; it kept the correct jsmn_init from ever being banked. `fix_invalid_escapes`
strips only the stray backslash, and only inside normal string/char literals.
"""
from __future__ import annotations

from alchemist.implementer.scrubber import fix_invalid_escapes, scrub_rust


def test_strips_bracket_escapes_keeps_valid_ones():
    src = r'''let s = " \t\n\r\"{}\[\]:,";'''
    out, n = fix_invalid_escapes(src)
    assert n == 2                       # \[ and \]
    assert r"\[" not in out and r"\]" not in out
    assert "[" in out and "]" in out
    for keep in (r"\t", r"\n", r"\r", r"\""):   # valid escapes untouched
        assert keep in out


def test_char_literal_escape():
    out, n = fix_invalid_escapes(r"""let c = '\[';""")
    assert n == 1 and out == "let c = '[';"


def test_valid_only_string_unchanged():
    src = r'''let v = "valid \n \t \x41 \u{1F600} and \\ backslash";'''
    out, n = fix_invalid_escapes(src)
    assert n == 0 and out == src


def test_raw_strings_and_comments_untouched():
    for src in (r'''let r = r"raw \[ stays \] here";''',
                r'''// a comment with \[ escapes \]''',
                r'''/* block \{ comment \} */'''):
        out, n = fix_invalid_escapes(src)
        assert n == 0 and out == src


def test_multiple_literals_in_one_line():
    src = r'''let a = "\[x"; let b = "\]y"; let ok = "\n";'''
    out, n = fix_invalid_escapes(src)
    assert n == 2
    assert r"\n" in out and r"\[" not in out and r"\]" not in out


def test_wired_into_scrub_rust():
    fixed, notes = scrub_rust(
        'pub fn f() -> bool { " \\t{}\\[\\]".contains(\'a\') }')
    assert r"\[" not in fixed and r"\]" not in fixed
    assert r"\t" in fixed
    assert any("invalid backslash-escape" in note for note in notes)
