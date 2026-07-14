"""Bare tag-form C enums (`enum http_errno { ... }`, no typedef) used directly in
signatures must resolve to i32, or the extractor's HttpErrno/HttpMethod/State/... are
undefined types that break the whole crate (http-parser E0425 x6). Regression for
collect_enum_tags + the signature normalization in inject_state_shared_types."""

from __future__ import annotations

from pathlib import Path

from alchemist.verifier.struct_lift import (
    collect_enum_tags, rust_struct_name, inject_state_shared_types,
)

_HP = """
enum http_errno { HPE_OK, HPE_CB_message_begin };
enum http_method { HTTP_DELETE, HTTP_GET };
enum state { s_dead = 1, s_start_req };
const char * http_errno_name(enum http_errno err) { return 0; }
const char * http_method_str(enum http_method m) { return 0; }
enum state parse_url_char(enum state s, const char ch) { return s; }
"""


class _I:
    def __init__(self, n, rt): self.name, self.rust_type = n, rt
class _A:
    def __init__(self, n, ins, ret): self.name, self.inputs, self.return_type, self.outputs = n, ins, ret, []
class _M:
    def __init__(self, algs): self.algorithms, self.shared_types = algs, []


def test_collect_bare_enum_tags(tmp_path):
    (tmp_path / "http_parser.c").write_text(_HP, encoding="utf-8")
    tags = collect_enum_tags(str(tmp_path))
    assert {"http_errno", "http_method", "state"} <= set(tags)
    assert {rust_struct_name(t) for t in tags} >= {"HttpErrno", "HttpMethod", "State"}


def test_bare_enum_signature_refs_resolve_to_i32(tmp_path):
    (tmp_path / "http_parser.c").write_text(_HP, encoding="utf-8")
    specs = [_M([
        _A("http_errno_name", [_I("err", "HttpErrno")], "&'static str"),
        _A("http_method_str", [_I("m", "HttpMethod")], "&'static str"),
        _A("parse_url_char", [_I("s", "State"), _I("ch", "u8")], "State"),
    ])]
    inject_state_shared_types(str(tmp_path), specs)
    algs = {a.name: a for a in specs[0].algorithms}
    assert algs["http_errno_name"].inputs[0].rust_type == "i32"
    assert algs["http_errno_name"].return_type == "&'static str"  # str_lookup preserved
    assert algs["http_method_str"].inputs[0].rust_type == "i32"
    assert algs["parse_url_char"].inputs[0].rust_type == "i32"
    assert algs["parse_url_char"].return_type == "i32"
