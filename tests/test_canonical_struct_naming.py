"""P1 keystone #1 — whole-program type coherence.

The extractor infers a Rust type per parameter independently, so ONE C struct
can surface as several incompatible Rust names across functions. For jsmn the C
`jsmn_parser *` came out as `Parser` in `jsmn_init` and `ParserState` in
`jsmn_parse` — a caller can't init a `Parser` then hand it to a fn wanting
`&mut ParserState`, so the workspace never links and the library yields 0
verified functions.

`inject_state_shared_types` must now pick ONE canonical Rust name per C struct
subject-wide, rewrite every signature to it, and emit exactly one shared type
per struct. These tests drive the real `subjects/jsmn` C source (for struct
fields + signatures) with hand-built specs that reproduce the extractor's split,
so they need no model and are fully deterministic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter
from alchemist.verifier.struct_lift import (
    _bare_struct_name,
    inject_state_shared_types,
)

JSMN = Path(__file__).resolve().parent.parent / "subjects" / "jsmn"

pytestmark = pytest.mark.skipif(
    not (JSMN / "jsmn.h").exists(), reason="jsmn subject not vendored"
)


def _param(name: str, rust_type: str) -> Parameter:
    return Parameter(name=name, rust_type=rust_type, description="")


def _alg(name: str, inputs: list[Parameter]) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name, display_name=name, category="data_structure", description="",
        inputs=inputs,
    )


def _jsmn_module_with_split() -> ModuleSpec:
    """jsmn_init sees `&mut Parser`, jsmn_parse sees `&mut ParserState` for the
    SAME C `jsmn_parser *` — plus jsmn_parse's `tokens: jsmntok_t *` as Token."""
    return ModuleSpec(
        name="jsmn", display_name="jsmn", description="",
        algorithms=[
            _alg("jsmn_init", [_param("parser", "&mut Parser")]),
            _alg("jsmn_parse", [
                _param("parser", "&mut ParserState"),
                _param("js", "&str"),
                _param("len", "usize"),
                _param("tokens", "Option<&mut [Token]>"),
                _param("num_tokens", "u32"),
            ]),
        ],
    )


def test_parser_struct_resolves_to_one_canonical_name():
    mod = _jsmn_module_with_split()
    inject_state_shared_types(str(JSMN), [mod])

    parser_types = {
        _bare_struct_name(inp.rust_type)
        for alg in mod.algorithms
        for inp in alg.inputs
        if inp.name == "parser"
    }
    assert parser_types == {"ParserState"}, (
        f"jsmn_parser must collapse to one canonical Rust type, got {parser_types}"
    )


def test_one_shared_type_emitted_per_canonical_struct():
    mod = _jsmn_module_with_split()
    n = inject_state_shared_types(str(JSMN), [mod])

    names = [st.name for st in (mod.shared_types or [])]
    # jsmn_parser -> ParserState (canonical), jsmntok_t -> Token: two structs,
    # each emitted exactly once (no ParserState AND Parser duplicate).
    assert "ParserState" in names, names
    assert "Parser" not in names, f"non-canonical alias leaked into emission: {names}"
    assert names.count("ParserState") == 1, f"duplicate emission: {names}"
    assert "Token" in names, f"non-first struct param (tokens) not carried: {names}"
    assert n == len(names)


def test_consistent_naming_is_left_untouched():
    """A subject that already names a struct consistently (rc4-style: one Rust
    name everywhere) must be unchanged — canonical == the single existing name."""
    mod = ModuleSpec(
        name="jsmn", display_name="jsmn", description="",
        algorithms=[
            _alg("jsmn_init", [_param("parser", "&mut Parser")]),
            _alg("jsmn_parse", [
                _param("parser", "&mut Parser"),
                _param("js", "&str"),
                _param("len", "usize"),
                _param("tokens", "Option<&mut [Token]>"),
                _param("num_tokens", "u32"),
            ]),
        ],
    )
    inject_state_shared_types(str(JSMN), [mod])
    parser_types = {
        _bare_struct_name(inp.rust_type)
        for alg in mod.algorithms for inp in alg.inputs if inp.name == "parser"
    }
    assert parser_types == {"Parser"}
