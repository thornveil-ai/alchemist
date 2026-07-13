"""P1 keystone #2 — the parser-class oracle.

Differentially verify a `parse(input) -> token array + return code` function against
the compiled C reference on fuzzed valid/malformed/truncated inputs. No existing oracle
covered this shape (the output is a variable-length struct array plus a signed return,
not a scalar or byte buffer), so jsmn — and the recursive-descent core of parson /
http-parser — could never be verified. These tests drive the real `subjects/jsmn` C
source with hand-built specs mirroring the length-folded lifted signature.

The classifier + ifdef-scoped token-overlay checks are model-free and fast. The token
CAPTURE check compiles the jsmn DLL (skipped when gcc is unavailable).
"""
from __future__ import annotations

import ctypes
import shutil
from pathlib import Path

import pytest

from alchemist.verifier import struct_lift
from alchemist.verifier.auto_config import (
    collect_subject_signatures,
    classify_parse_sequence,
    fuzz_parse_sequence_vectors,
    _compiled_token_cls,
    _ctypes_struct_cls,
    _ifdef_guarded_fields,
    _extract_struct_body,
    _PARSE_FUZZ_INPUTS,
)
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter

JSMN = Path(__file__).resolve().parent.parent / "subjects" / "jsmn"
OBJECT, ARRAY, STRING, PRIMITIVE = 1, 2, 4, 8  # jsmn type flags (1<<0..1<<3)

pytestmark = pytest.mark.skipif(
    not (JSMN / "jsmn.h").exists(), reason="jsmn subject not vendored"
)


def _p(name, rt):
    return Parameter(name=name, rust_type=rt, description="")


def _specs():
    """jsmn_init(&mut ParserState) + jsmn_parse folded to
    (&mut ParserState, js: &str, tokens: Option<&mut [Token]>) -> Result<i32, E>."""
    return [ModuleSpec(
        name="jsmn", display_name="jsmn", description="",
        algorithms=[
            AlgorithmSpec(name="jsmn_init", display_name="jsmn_init",
                          category="data_structure", description="",
                          inputs=[_p("parser", "&mut ParserState")]),
            AlgorithmSpec(name="jsmn_parse", display_name="jsmn_parse",
                          category="data_structure", description="",
                          return_type="Result<i32, JsmnError>",
                          inputs=[_p("parser", "&mut ParserState"),
                                  _p("js", "&str"),
                                  _p("tokens", "Option<&mut [Token]>")]),
        ])]


def _group():
    by_name = {s.name: s for s in collect_subject_signatures(JSMN)}
    structs = struct_lift.structs_in_dir(JSMN)
    return classify_parse_sequence(by_name, structs, str(JSMN), _specs()), structs


def test_classifies_init_plus_parse():
    group, _ = _group()
    assert group is not None
    assert group["struct"] == "jsmn_parser"
    assert group["tok_struct"] == "jsmntok_t"
    assert group["init"][0] == "jsmn_init"
    assert group["parse"][0] == "jsmn_parse"


def test_ifdef_guarded_field_is_scoped_to_struct_body():
    """The file-wide `#ifndef JSMN_HEADER` guard around the impl must NOT mask real
    fields — only jsmntok's `#ifdef JSMN_PARENT_LINKS` `parent` is dropped."""
    guarded = _ifdef_guarded_fields(
        str(JSMN), "jsmntok_t",
        [f.name for f in struct_lift.structs_in_dir(JSMN)["jsmntok_t"]])
    assert guarded == {"parent"}, guarded


def test_extract_struct_body_typedef_form():
    text = "typedef struct foo {\n  int a;\n  int b;\n} foo;\n"
    body = _extract_struct_body(text, "foo")
    assert body is not None and "int a;" in body and "int b;" in body


def test_token_overlay_matches_compiled_layout():
    group, _ = _group()
    _, kept = _compiled_token_cls(group["tok_struct"], group["tok_fields"], group["guarded"])
    assert kept == ["type", "start", "end", "size"]  # parent dropped


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc required to build jsmn DLL")
def test_captures_c_token_output_byte_exact(tmp_path):
    from alchemist.verifier.auto_ffi import build_c_dll
    from alchemist.verifier.build_c_dll import discover_c_build
    group, _ = _group()
    c_files, inc = discover_c_build(JSMN)
    dll_path = tmp_path / "cref.dll"
    build = build_c_dll(c_files, dll_path, include_dirs=inc)
    if not build.success:
        pytest.skip(f"jsmn DLL build failed: {build}")
    dll = ctypes.CDLL(str(dll_path))
    StateC = _ctypes_struct_cls(group["struct"], group["fields"])
    TokC, _ = _compiled_token_cls(group["tok_struct"], group["tok_fields"], group["guarded"])
    dll.jsmn_init.restype = None
    dll.jsmn_init.argtypes = (ctypes.POINTER(StateC),)
    dll.jsmn_parse.restype = ctypes.c_int
    dll.jsmn_parse.argtypes = (ctypes.POINTER(StateC), ctypes.c_char_p,
                               ctypes.c_size_t, ctypes.POINTER(TokC), ctypes.c_uint)

    def parse(js: bytes):
        st = StateC(); dll.jsmn_init(ctypes.byref(st))
        toks = (TokC * 128)()
        r = int(dll.jsmn_parse(ctypes.byref(st), js, len(js), toks, 128))
        return r, [(toks[i].type, toks[i].start, toks[i].end, toks[i].size)
                   for i in range(max(r, 0))]

    r, toks = parse(b'{"a":1}')
    assert r == 3
    assert toks[0] == (OBJECT, 0, 7, 1)
    assert toks[1] == (STRING, 2, 3, 1)
    assert toks[2] == (PRIMITIVE, 5, 6, 0)
    assert parse(b"[1,2,3]")[0] == 4  # array + 3 primitives
    # the oracle must faithfully capture C's negative error returns where they occur
    assert any(parse(js)[0] < 0 for js in _PARSE_FUZZ_INPUTS)

    # full oracle: well-formed rust_body differential vectors
    vecs = fuzz_parse_sequence_vectors(dll, group, _specs())
    bodies = [v.expected_output for v in vecs["jsmn_parse"]]
    assert bodies
    assert any("assert_eq!(n as i64, 3" in b for b in bodies)   # a 3-token Ok case
    assert any("expected error" in b for b in bodies)           # an error case
    for b in bodies:
        assert "jsmn_init(&mut st)" in b and "jsmn_parse(" in b
        assert "Vec<super::Token>" in b
