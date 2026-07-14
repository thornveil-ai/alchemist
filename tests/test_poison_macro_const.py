"""A `#define NAME VALUE` whose VALUE is a bare identifier is only a sound Rust const
if VALUE is another defined const/enum. When it isn't, VALUE is a dangling reference and
`pub const NAME = VALUE` is E0425 that breaks the WHOLE crate. Libraries plant such
POISON macros to forbid a call at compile time (parson: `#define sscanf
THINK_TWICE_ABOUT_USING_SSCANF`, `#define strcpy USE_MEMCPY_INSTEAD_OF_STRCPY`). The
constants extractor must drop these, while keeping real consts and valid aliases.
"""
from __future__ import annotations

from alchemist.extractor.constants_extractor import extract_constants


def _consts(src):
    rep = extract_constants(src, c_file="t.h")
    return {c.name: c.rust_expr for c in rep.extracted}, dict(rep.skipped)


def test_drops_dangling_poison_macros():
    kept, skipped = _consts(
        "#define sscanf THINK_TWICE_ABOUT_USING_SSCANF\n"
        "#define strcpy USE_MEMCPY_INSTEAD_OF_STRCPY\n"
        "#define MAX_TOKENS 128\n"
    )
    assert "sscanf" not in kept and "strcpy" not in kept
    assert kept.get("MAX_TOKENS") == "128"
    assert "THINK_TWICE" in skipped.get("sscanf", "")


def test_keeps_alias_to_defined_const():
    kept, _ = _consts("#define MAX_TOKENS 128\n#define DEFAULT_CAP MAX_TOKENS\n")
    assert kept.get("MAX_TOKENS") == "128"
    assert kept.get("DEFAULT_CAP") == "MAX_TOKENS"  # references a DEFINED const → kept


def test_keeps_numeric_and_literal_consts():
    kept, _ = _consts("#define FLAG 1\n#define PI 3.14\n#define NAME \"parson\"\n")
    assert kept.get("FLAG") == "1"
    assert "PI" in kept
