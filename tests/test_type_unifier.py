"""Whole-workspace type coherence (the Phase 2 / moonshot foundation).

The extractor maps the SAME C type to different Rust types across functions.
The unifier canonicalizes REGISTERED types (ct_data → TreeElement) while
refusing to touch legitimately-polymorphic C types (int, void*, z_streamp).
"""

from __future__ import annotations

from alchemist.architect.type_unifier import (
    CanonicalType,
    render_canonical_struct,
    unify_types,
)
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter


def _alg(name, params):
    return AlgorithmSpec(
        name=name, display_name=name, category="compression", description="",
        inputs=[Parameter(name=n, rust_type=t, description="") for n, t in params],
        return_type="()")


def _analysis(fns: dict[str, list[tuple[str, str]]]) -> dict:
    """Build an analysis.json-shaped dict: fn -> [(param_name, c_type)]."""
    return {"files": {"x.c": {"functions": [
        {"name": n, "params": [{"name": pn, "type": ct} for pn, ct in ps]}
        for n, ps in fns.items()
    ]}}}


def test_ct_data_fracture_unifies_to_slice_of_treeelement():
    """ct_data mapped to TreeElement, HuffmanTree, and (u16,u16) across three
    functions must all become &[TreeElement] / &mut [TreeElement]."""
    specs = [ModuleSpec(name="trees", display_name="", description="", algorithms=[
        _alg("pqdownheap", [("tree", "&[TreeElement]")]),
        _alg("gen_codes",  [("tree", "&mut [TreeElement]")]),
        _alg("compress_block", [("ltree", "&HuffmanTree"), ("dtree", "&HuffmanTree")]),
        _alg("scan_tree",  [("tree", "Vec<(u16, u16)>")]),
    ])]
    analysis = _analysis({
        "pqdownheap": [("tree", "ct_data")],
        "gen_codes":  [("tree", "ct_data")],
        "compress_block": [("ltree", "ct_data"), ("dtree", "ct_data")],
        "scan_tree":  [("tree", "ct_data")],
    })
    rep = unify_types(specs, analysis)
    calls = {(a.name, p.name): p.rust_type
             for a in specs[0].algorithms for p in a.inputs}
    assert calls[("pqdownheap", "tree")] == "&[TreeElement]"
    assert calls[("gen_codes", "tree")] == "&mut [TreeElement]"        # mut kept
    assert calls[("compress_block", "ltree")] == "&[TreeElement]"      # struct→slice repaired
    assert calls[("compress_block", "dtree")] == "&[TreeElement]"
    assert calls[("scan_tree", "tree")] == "&[TreeElement]"            # tuple→slice
    assert rep.canonical["ct_data"] == "TreeElement"
    # pqdownheap/gen_codes were already coherent; only the 3 incoherent
    # params (compress_block ltree+dtree, scan_tree) were rewritten.
    assert rep.rewrites == 3


def test_polymorphic_c_types_are_never_unified():
    """z_streamp is a deflate stream in one fn and an inflate stream in
    another — unifying it would corrupt the workspace. int/void* likewise."""
    specs = [ModuleSpec(name="m", display_name="", description="", algorithms=[
        _alg("deflate", [("strm", "&mut DeflateStream")]),
        _alg("inflate", [("strm", "&mut InflateStream")]),
        _alg("f", [("x", "i32")]),
        _alg("g", [("x", "u32")]),
        _alg("cb", [("ctx", "Context")]),
        _alg("cb2", [("ctx", "Vec<u8>")]),
    ])]
    analysis = _analysis({
        "deflate": [("strm", "z_streamp")],
        "inflate": [("strm", "z_streamp")],
        "f": [("x", "int")], "g": [("x", "int")],
        "cb": [("ctx", "void *")], "cb2": [("ctx", "void *")],
    })
    rep = unify_types(specs, analysis)
    assert "z_streamp" not in rep.canonical
    assert "int" not in rep.canonical
    assert "void" not in rep.canonical
    calls = {(a.name, p.name): p.rust_type
             for a in specs[0].algorithms for p in a.inputs}
    assert calls[("deflate", "strm")] == "&mut DeflateStream"  # untouched
    assert calls[("inflate", "strm")] == "&mut InflateStream"  # untouched


def test_custom_registry_extends_canonicalization():
    reg = {"my_node": CanonicalType(
        c_type="my_node", rust_name="MyNode",
        fields=(("a", "u16"), ("b", "u16")), container="slice")}
    specs = [ModuleSpec(name="m", display_name="", description="", algorithms=[
        _alg("f", [("n", "&SomeWrapper")]),
    ])]
    analysis = _analysis({"f": [("n", "my_node")]})
    rep = unify_types(specs, analysis, registry=reg)
    assert specs[0].algorithms[0].inputs[0].rust_type == "&[MyNode]"
    assert "MyNode" in rep.structs


def test_canonical_treeelement_has_complete_field_set():
    """The lossy extractor dropped `dad`; the canonical carries all four
    ct_data slots (freq/code and dad/len)."""
    specs = [ModuleSpec(name="m", display_name="", description="", algorithms=[
        _alg("f", [("tree", "&[TreeElement]")])])]
    rep = unify_types(specs, _analysis({"f": [("tree", "ct_data")]}))
    fields = dict(rep.structs["TreeElement"].fields)
    assert set(fields) == {"freq", "code", "dad", "len"}
    rust = render_canonical_struct(rep.structs["TreeElement"])
    assert "pub struct TreeElement" in rust
    assert "pub dad: u16," in rust
    assert "Copy" in rust  # tree nodes are Copy


def test_no_analysis_is_a_noop():
    specs = [ModuleSpec(name="m", display_name="", description="", algorithms=[
        _alg("f", [("tree", "&[TreeElement]")])])]
    rep = unify_types(specs, {"files": {}})
    assert rep.rewrites == 0
