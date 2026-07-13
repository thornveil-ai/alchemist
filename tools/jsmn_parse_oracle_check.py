"""Keystone #2 validation (model-free): the parser-class oracle must CLASSIFY jsmn's
init+parse and CAPTURE the compiled C token output byte-exactly on fuzzed inputs.

Builds the real jsmn DLL, hand-builds specs mirroring the (length-folded) lifted
signature, runs classify_parse_sequence + fuzz_parse_sequence_vectors, and asserts:
 (1) the token overlay drops the ifdef-guarded `parent` and keeps type/start/end/size;
 (2) the C reference captures the correct tokens for known JSON (e.g. {"a":1} -> 3
     tokens OBJECT/STRING/PRIMITIVE with correct spans);
 (3) malformed/truncated inputs capture C's negative error return;
 (4) each emitted rust_body test is well-formed (return assert + per-token asserts).
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from alchemist.verifier.auto_ffi import build_c_dll
from alchemist.verifier.build_c_dll import discover_c_build
from alchemist.verifier import struct_lift
from alchemist.verifier.auto_config import (
    collect_subject_signatures,
    classify_parse_sequence,
    fuzz_parse_sequence_vectors,
    _compiled_token_cls,
    _ctypes_struct_cls,
)
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter

JSMN = Path("subjects/jsmn").resolve()
# jsmn token type flags (1<<0 .. 1<<3)
OBJECT, ARRAY, STRING, PRIMITIVE = 1, 2, 4, 8


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


def main() -> int:
    specs = _specs()
    by_name = {s.name: s for s in collect_subject_signatures(JSMN)}
    structs = struct_lift.structs_in_dir(JSMN)

    group = classify_parse_sequence(by_name, structs, str(JSMN), specs)
    assert group is not None, "FAIL: classify_parse_sequence did not recognize jsmn"
    print(f"classified: state={group['struct']} tok={group['tok_struct']} "
          f"init={group['init'][0]} parse={group['parse'][0]}")
    print(f"guarded (dropped) fields: {group['guarded']}")
    assert group["guarded"] == {"parent"}, f"expected only 'parent' guarded, got {group['guarded']}"

    _, kept = _compiled_token_cls(group["tok_struct"], group["tok_fields"], group["guarded"])
    print(f"kept token fields (compiled layout): {kept}")
    assert kept == ["type", "start", "end", "size"], f"unexpected kept fields: {kept}"

    # Build the DLL and directly cross-check the C capture on a known input.
    c_files, inc = discover_c_build(JSMN)
    work = JSMN / ".alchemist" / "cvec"
    work.mkdir(parents=True, exist_ok=True)
    dll_path = work / ("cref.dll" if os.name == "nt" else "libcref.so")
    build = build_c_dll(c_files, dll_path, include_dirs=inc)
    assert build.success, f"FAIL: DLL build failed: {build}"
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
    print(f'{{"a":1}} -> r={r} toks={toks}')
    assert r == 3, f"expected 3 tokens, got {r}"
    assert toks[0][0] == OBJECT and toks[0][3] == 1, f"tok0 {toks[0]}"
    assert toks[1][0] == STRING and (toks[1][1], toks[1][2]) == (2, 3), f"tok1 {toks[1]}"
    assert toks[2][0] == PRIMITIVE and (toks[2][1], toks[2][2]) == (5, 6), f"tok2 {toks[2]}"

    r2, _ = parse(b"[1,2,3]")
    assert r2 == 4, f"[1,2,3] expected 4 tokens (array+3), got {r2}"
    # jsmn is lenient (returns partial counts on some malformed input), so probe the
    # corpus: the oracle must faithfully capture C's negative ERROR returns where they
    # occur — not assume any specific input errors.
    from alchemist.verifier.auto_config import _PARSE_FUZZ_INPUTS
    errored = [(js, parse(js)[0]) for js in _PARSE_FUZZ_INPUTS if parse(js)[0] < 0]
    print(f"inputs with C error return: {[(js, r) for js, r in errored][:6]}")
    assert errored, "no fuzz input produced a C error return — error path not exercised"

    # Full oracle: generate rust_body vectors and sanity-check their structure.
    vecs = fuzz_parse_sequence_vectors(dll, group, specs)
    assert "jsmn_parse" in vecs and vecs["jsmn_parse"], "no parse vectors emitted"
    bodies = [v.expected_output for v in vecs["jsmn_parse"]]
    print(f"emitted {len(bodies)} rust_body parse vectors")
    # a valid-object vector must assert both the return and each token field
    obj_vec = next((b for b in bodies if 'from_utf8' in b and 'assert_eq!(n as i64, 3' in b), None)
    assert obj_vec is not None, "no 3-token Ok vector found"
    assert 'toks[0].r#type' in obj_vec or 'toks[0].type_' in obj_vec, \
        "token field access not keyword-sanitized"
    # a malformed vector must assert the error branch
    err_vec = next((b for b in bodies if 'expected error' in b), None)
    assert err_vec is not None, "no error-return vector found"
    # init post-state observer (jsmn_init: pos=0, toknext=0, toksuper=-1)
    assert "jsmn_init" in vecs and vecs["jsmn_init"], "no init observer vectors emitted"
    init_body = vecs["jsmn_init"][0].expected_output
    assert "jsmn_init(&mut st)" in init_body and "toksuper" in init_body, init_body
    assert "-1" in init_body, "toksuper post-init should be -1"
    print(f"init observer: {len(vecs['jsmn_init'])} vectors, asserts parser post-state")
    # every body references init + parse + the token buffer
    for b in bodies:
        assert "jsmn_init(&mut st)" in b and "jsmn_parse(" in b and "Vec<super::Token>" in b

    print("\nKEYSTONE#2 PASS: parser-class oracle classifies jsmn, captures C token "
          "output byte-exact (valid + malformed), and emits well-formed differential tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
