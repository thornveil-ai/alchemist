"""P1: header-only C libraries (jsmn, stb-style single-header libs) put their
ENTIRE implementation in a `.h`. The module detector previously grouped only
`.c` files into modules and treated every `.h` as declarations-only, so a
header-only lib produced ZERO modules → nothing extracted → 0/0 functions (the
dangerous invisible-failure class the refusal metric can't see).

The parser only records functions that have a body, so a `.h` with a non-empty
`functions` list carries real code and must be a module of its own."""

from __future__ import annotations

from alchemist.analyzer.module_detector import ModuleDetector


def _fn(name, lines=20):
    return {"name": name, "calls": [], "local_vars": [], "params": [],
            "line_count": lines}


def _detect(parsed):
    return ModuleDetector().detect(parsed, call_graph={})


def test_header_only_library_becomes_a_module():
    # All code lives in the .h; the only .c is a main() harness.
    parsed = {
        "/x/jsmn.h": {"functions": [_fn("jsmn_parse", 120), _fn("jsmn_init")],
                      "structs": [], "typedefs": {}, "macros": []},
        "/x/jsmn_ref.c": {"functions": [_fn("main", 5)],
                          "structs": [], "typedefs": {}, "macros": []},
    }
    mods = _detect(parsed)
    names = {m["name"] for m in mods}
    assert "jsmn" in names, f"header-only module missing: {names}"
    jsmn = next(m for m in mods if m["name"] == "jsmn")
    assert len(jsmn["functions"]) == 2


def test_declaration_only_header_is_not_a_module():
    # A classic .c + prototype-only .h: the header has NO function bodies, so it
    # must NOT become its own module (only its structs/typedefs merge into the .c).
    parsed = {
        "/x/foo.h": {"functions": [], "structs": [{"name": "Foo"}],
                     "typedefs": {"u8": "unsigned char"}, "macros": []},
        "/x/foo.c": {"functions": [_fn("foo_do", 30)],
                     "structs": [], "typedefs": {}, "macros": []},
    }
    mods = _detect(parsed)
    names = {m["name"] for m in mods}
    assert "foo" in names
    assert "foo_h" not in names and "foo" == next(m["name"] for m in mods if m["name"] == "foo")
    # the .c module should have absorbed the header's struct/typedef
    foo = next(m for m in mods if m["name"] == "foo")
    assert len(foo["functions"]) == 1


def test_definition_header_does_not_self_duplicate_structs():
    # A definition-bearing header is in both the groups and headers dicts; the
    # association step must not merge it with itself (would duplicate structs).
    parsed = {
        "/x/lib.h": {"functions": [_fn("lib_run", 40)],
                     "structs": [{"name": "State"}],
                     "typedefs": {"u32": "unsigned int"}, "macros": []},
    }
    mods = _detect(parsed)
    lib = next(m for m in mods if m["name"] == "lib")
    # exactly one State struct, not two (self-association would duplicate).
    def _sname(s):
        return s.get("name") if isinstance(s, dict) else s
    structs = lib.get("structs", [])
    assert sum(1 for s in structs if _sname(s) == "State") <= 1
