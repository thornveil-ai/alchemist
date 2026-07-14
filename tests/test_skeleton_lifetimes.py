"""Skeleton lifetime elision. A borrow-returning function needs an explicit lifetime or
the skeleton won't compile (E0106) — this blocked EVERY parson getter (e.g.
`json_object_get_value(object: &JsonObject, name: &str) -> Option<&JsonValue>`), so the
whole crate failed to compile and 0 functions were even attempted. When any input borrows,
tie the return borrow to the inputs via a named `'a`; with no borrowed input (a pointer to
static data) fall back to `'static`. Owned returns are untouched.
"""
from __future__ import annotations

from alchemist.implementer.skeleton import _fn_signature
from alchemist.extractor.schemas import AlgorithmSpec, Parameter


def _p(n, t):
    return Parameter(name=n, rust_type=t, description="")


def _a(name, inputs, ret):
    return AlgorithmSpec(name=name, display_name=name, category="data_structure",
                         description="", inputs=inputs, return_type=ret)


def test_borrow_return_ties_to_borrowed_inputs():
    sig = _fn_signature(_a("json_object_get_value",
                           [_p("object", "&JsonObject"), _p("name", "&str")],
                           "Option<&JsonValue>"))
    assert sig == ("pub fn json_object_get_value<'a>(object: &'a JsonObject, "
                   "name: &'a str) -> Option<&'a JsonValue>")


def test_option_ref_str():
    sig = _fn_signature(_a("json_object_get_string",
                           [_p("object", "&JsonObject"), _p("name", "&str")],
                           "Option<&str>"))
    assert sig.endswith("-> Option<&'a str>") and "<'a>" in sig


def test_mut_borrow_input_and_return():
    sig = _fn_signature(_a("f", [_p("s", "&mut State"), _p("k", "&[u8]")], "&[u8]"))
    assert sig == "pub fn f<'a>(s: &'a mut State, k: &'a [u8]) -> &'a [u8]"


def test_no_borrowed_input_falls_back_to_static():
    sig = _fn_signature(_a("get_crc_table", [], "&[u32]"))
    assert sig == "pub fn get_crc_table() -> &'static [u32]"


def test_owned_return_untouched():
    assert _fn_signature(_a("add", [_p("a", "u32"), _p("b", "u32")], "u32")) \
        == "pub fn add(a: u32, b: u32) -> u32"
    assert "<'a>" not in _fn_signature(_a("parse", [_p("js", "&str")], "Result<usize, E>"))


def test_already_lifetimed_not_double_annotated():
    sig = _fn_signature(_a("g", [], "&'static str"))
    assert sig.count("'static") == 1 and "'a" not in sig
