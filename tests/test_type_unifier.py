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


def _shared(name, rust_def=None, fields=None):
    from alchemist.extractor.schemas import SharedType, TypeField
    return SharedType(
        name=name, rust_definition=rust_def or "", description="",
        fields=[TypeField(name=n, rust_type=t, description="") for n, t in (fields or [])])


def test_state_fields_in_rust_definition_are_unified():
    """DeflateState tree fields live in a raw rust_definition string as
    Vec<(u16,u16)> — the leak the param pass alone can't reach."""
    ds = _shared("DeflateState", rust_def=(
        "#[derive(Debug, Default)]\n"
        "pub struct DeflateState {\n"
        "    pub status: i32,\n"
        "    pub dyn_ltree: Vec<(u16, u16)>,\n"
        "    pub dyn_dtree: Vec<(u16, u16)>,\n"
        "    pub bl_tree: Vec<(u16, u16)>,\n"
        "    pub heap: Vec<i32>,\n"
        "}"))
    specs = [ModuleSpec(name="types", display_name="", description="",
                        algorithms=[], shared_types=[ds])]
    rep = unify_types(specs, {"files": {}})
    rd = specs[0].shared_types[0].rust_definition
    assert "dyn_ltree: Vec<TreeElement>" in rd
    assert "dyn_dtree: Vec<TreeElement>" in rd
    assert "bl_tree: Vec<TreeElement>" in rd
    assert "Vec<(u16" not in rd            # no tuple leak left
    assert "heap: Vec<i32>" in rd          # non-tree field untouched
    assert rep.field_rewrites == 3


def test_duplicate_struct_is_dropped_and_references_rewritten():
    """HuffmanNode is a byte-identical duplicate of TreeElement — its
    references become TreeElement and its definition is dropped."""
    huff = _shared("HuffmanNode", rust_def="pub struct HuffmanNode { pub freq: u16 }")
    tdesc = _shared("TreeDesc", rust_def=(
        "pub struct TreeDesc {\n    pub dyn_tree: Vec<HuffmanNode>,\n"
        "    pub max_code: i32,\n}"))
    tree_el = _shared("TreeElement", rust_def=(
        "pub struct TreeElement { pub freq: u16, pub code: u16, pub len: u8 }"))
    specs = [ModuleSpec(name="types", display_name="", description="",
                        algorithms=[], shared_types=[tree_el, huff, tdesc])]
    rep = unify_types(specs, {"files": {}})
    names = {s.name for s in specs[0].shared_types}
    assert "HuffmanNode" not in names          # dropped
    assert "HuffmanNode" in rep.dropped_structs
    td = next(s for s in specs[0].shared_types if s.name == "TreeDesc")
    assert "dyn_tree: Vec<TreeElement>" in td.rust_definition
    # Canonical struct materialized with the COMPLETE field set (dad added)
    te = next(s for s in specs[0].shared_types if s.name == "TreeElement")
    assert "pub dad: u16," in te.rust_definition


def test_typefield_shared_types_are_unified():
    st = _shared("S", fields=[("tree", "Vec<(u16, u16)>"), ("n", "u32")])
    specs = [ModuleSpec(name="m", display_name="", description="",
                        algorithms=[], shared_types=[st])]
    unify_types(specs, {"files": {}})
    fields = {f.name: f.rust_type for f in specs[0].shared_types[0].fields}
    assert fields["tree"] == "Vec<TreeElement>"
    assert fields["n"] == "u32"


def test_param_and_state_field_are_now_call_compatible():
    """The whole point: pqdownheap(&[TreeElement]) can be fed
    state.dyn_ltree (Vec<TreeElement>) after unification."""
    ds = _shared("DeflateState", rust_def=(
        "pub struct DeflateState {\n    pub dyn_ltree: Vec<(u16, u16)>,\n}"))
    specs = [ModuleSpec(name="trees", display_name="", description="", shared_types=[ds],
                        algorithms=[_alg("pqdownheap", [("tree", "&HuffmanTree")])])]
    analysis = _analysis({"pqdownheap": [("tree", "ct_data")]})
    unify_types(specs, analysis)
    param = specs[0].algorithms[0].inputs[0].rust_type
    rd = specs[0].shared_types[0].rust_definition
    assert param == "&[TreeElement]"
    assert "dyn_ltree: Vec<TreeElement>" in rd  # &state.dyn_ltree coerces to &[TreeElement]


def test_field_overrides_fix_scalar_collapsed_descriptors():
    """DeflateState.l_desc/d_desc/bl_desc collapsed to u32; build_bl_tree
    does s.l_desc.max_code, which needs TreeDesc. No correlation/alias can
    reach it — only an explicit override."""
    ds = _shared("DeflateState", rust_def=(
        "pub struct DeflateState {\n"
        "    pub opt_len: u64,\n"
        "    pub l_desc: u32,\n"
        "    pub d_desc: u32,\n"
        "    pub bl_desc: u32,\n"
        "}"))
    specs = [ModuleSpec(name="types", display_name="", description="",
                        algorithms=[], shared_types=[ds])]
    unify_types(specs, {"files": {}})
    rd = specs[0].shared_types[0].rust_definition
    assert "pub l_desc: TreeDesc," in rd
    assert "pub d_desc: TreeDesc," in rd
    assert "pub bl_desc: TreeDesc," in rd
    assert "pub opt_len: u64," in rd   # untouched


def test_param_override_fixes_gen_bitlen_mutability():
    """gen_bitlen mutates the tree's Len but was inferred as &TreeDesc;
    the param override makes it &mut TreeDesc like build_tree."""
    specs = [ModuleSpec(name="trees", display_name="", description="", algorithms=[
        _alg("gen_bitlen", [("s", "&mut DeflateState"), ("desc", "&TreeDesc")])])]
    unify_types(specs, {"files": {}})
    types = {p.name: p.rust_type for p in specs[0].algorithms[0].inputs}
    assert types["desc"] == "&mut TreeDesc"


def test_field_additions_add_missing_sym_buf():
    """The extractor missed DeflateState.sym_buf/sym_next (active C uses the
    modern single sym_buf); the addition pass inserts them idempotently."""
    ds = _shared("DeflateState", rust_def=(
        "pub struct DeflateState {\n    pub last_lit: u32,\n}"))
    specs = [ModuleSpec(name="types", display_name="", description="",
                        algorithms=[], shared_types=[ds])]
    unify_types(specs, {"files": {}})
    rd = specs[0].shared_types[0].rust_definition
    assert "pub sym_buf: Vec<u8>," in rd
    assert "pub sym_next: u32," in rd
    # idempotent
    unify_types(specs, {"files": {}})
    assert specs[0].shared_types[0].rust_definition.count("pub sym_buf") == 1
