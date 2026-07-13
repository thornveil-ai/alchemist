"""P1: struct-carry must emit struct types referenced by NON-first / slice-element
params, not only the `params[0]` state struct. jsmn's `jsmn_parse` takes
`tokens: Option<&mut [Token]>` (C `jsmntok_t *`); without carrying `Token` the
skeleton fails to compile with `cannot find type Token`, so the whole library
produces 0 verified functions. Existing subjects (rc4/sha256) have only
byte-buffer non-first params, so they gain nothing and can't regress."""

from __future__ import annotations

from alchemist.verifier.struct_lift import _bare_struct_name, _RUST_PRIMS


def test_bare_struct_name_strips_containers():
    assert _bare_struct_name("Option<&mut [Token]>") == "Token"
    assert _bare_struct_name("&mut ParserState") == "ParserState"
    assert _bare_struct_name("&[u8]") == "u8"
    assert _bare_struct_name("&str") == "str"
    assert _bare_struct_name("Box<Node>") == "Node"
    assert _bare_struct_name("&mut [u32; 8]") == "u32"


def test_primitives_are_excluded():
    for p in ("u8", "u32", "usize", "str", "String", "bool", "char"):
        assert p in _RUST_PRIMS
    assert "Token" not in _RUST_PRIMS


def test_bare_struct_name_rejects_non_identifiers():
    assert _bare_struct_name("") is None
    assert _bare_struct_name(None) is None
