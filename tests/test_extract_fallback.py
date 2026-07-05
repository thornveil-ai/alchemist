"""Regression tests for the brace-matching C-function extractor fallback.

tree-sitter-c chokes on huge, macro-heavy functions (zlib's `inflate()`: a
`for(;;)switch` with embedded `#ifdef`s produces an ERROR node that corrupts
extraction of it and every function after it). `_extract_by_brace_match`
recovers these. These tests reproduce the exact failure shapes with inline C so
they run without the box or fixtures. See docs/PATH_TO_AUTONOMY.md (WS1).
"""

from pathlib import Path

from alchemist.implementer.reference_probe import (
    extract_c_function_body,
    _extract_by_brace_match,
    _blank_comments_strings,
)


def test_blank_preserves_length_and_positions():
    src = 'int x; /* } ; comment */ char *s = "a;}b"; // trailing\n'
    blanked = _blank_comments_strings(src)
    assert len(blanked) == len(src)
    # code delimiters outside literals survive
    assert blanked.count(";") == 2  # `int x;` and `char *s = ...;`
    # delimiters inside the comment/string are gone
    assert "comment" not in blanked
    assert "a;}b" not in blanked


def test_do_while_macro_then_comment_then_function():
    # Exactly the shape that fooled the `}`-backtrack: a do{}while(0) macro,
    # then a doc comment mentioning the function name (with ; and } inside),
    # then the real definition.
    src = (
        "#define PULLBYTE() do { hold += *next++; bits += 8; } while (0)\n"
        "\n"
        "/* inflate() uses a state machine; e.g. { case X: break; } and so on. */\n"
        "int ZEXPORT inflate(z_streamp strm, int flush) {\n"
        "    for (;;) switch (state->mode) {\n"
        "    case HEAD:\n"
        "        goto inf_leave;\n"
        "    }\n"
        "    return ret;\n"
        "}\n"
    )
    body = _extract_by_brace_match(src, "inflate")
    assert body is not None
    assert body.startswith("int ZEXPORT inflate(z_streamp strm, int flush)")
    assert body.rstrip().endswith("}")
    # must not include the preceding macro or comment
    assert "PULLBYTE" not in body
    assert "state machine" not in body


def test_ignores_calls_only_definition_matches():
    src = (
        "void caller(void) { helper(1, 2); helper(3, 4); }\n"
        "int helper(int a, int b) { return a + b; }\n"
    )
    body = _extract_by_brace_match(src, "helper")
    assert body is not None
    assert body.startswith("int helper(int a, int b)")
    assert "caller" not in body


def test_pointer_return_type_signature():
    src = "static char *dup(const char *s) { return copy(s); }\n"
    body = _extract_by_brace_match(src, "dup")
    assert body.startswith("static char *dup(const char *s)")


def test_string_with_braces_does_not_break_matching():
    src = 'int f(void) { const char *j = "{ not real }"; return 0; }\n'
    body = _extract_by_brace_match(src, "f")
    assert body is not None
    assert body.rstrip().endswith("}")
    assert '"{ not real }"' in body  # the string is preserved in the returned original


def test_missing_function_returns_none():
    assert _extract_by_brace_match("int a(void){return 0;}", "nope") is None


def test_real_zlib_inflate_if_source_available():
    # Opportunistic: only runs where the zlib subject exists (the box / a checkout).
    for root in (
        Path("subjects/zlib/inflate.c"),
        Path("/data/rigrun/projects/alchemist/subjects/zlib/inflate.c"),
    ):
        if root.exists():
            body = extract_c_function_body(root, "inflate")
            assert body is not None and len(body) > 10000
            assert body.lstrip().startswith("int ZEXPORT inflate")
            return
