"""P1 keystone #3 — ownership at library scale.

A pointer-linked / heap-allocating C data structure (linked list, tree, JSON DOM)
could never get a compilable Rust skeleton: struct-carry DROPPED every pointer
field, so `struct node { struct node *next; }` lost its `next` and no
list/tree/parson-class library could link. This lifts an owned pointer to a
carried struct into safe Rust — `T* next -> Option<Box<T>>`, a counted array
`T* items` + length -> `Vec<T>` — and emits the transitive closure of reachable
node types so the whole structure is defined.

emit_safe_struct tests are pure (hand-built fields). The transitive-closure test
drives inject_state_shared_types over a tiny real linked-list source.
"""
from __future__ import annotations

from pathlib import Path

from alchemist.verifier.struct_lift import (
    Field,
    emit_safe_struct,
    inject_state_shared_types,
    structs_in_dir,
)
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter


# ---- emit_safe_struct: the owned-pointer lift -----------------------------

def test_self_referential_pointer_lifts_to_option_box():
    node = [Field("val", "int", None, False), Field("next", "struct node", None, True)]
    out = emit_safe_struct("Node", node, c_to_rust={"node": "Node"})
    assert out is not None
    assert "pub next: Option<alloc::boxed::Box<Node>>," in out
    assert "pub val: i32," in out
    assert "next: None" in out  # Default


def test_binary_tree_two_owned_children():
    tnode = [Field("key", "int", None, False),
             Field("left", "struct tnode", None, True),
             Field("right", "struct tnode", None, True)]
    out = emit_safe_struct("TNode", tnode, c_to_rust={"tnode": "TNode"})
    assert "pub left: Option<alloc::boxed::Box<TNode>>," in out
    assert "pub right: Option<alloc::boxed::Box<TNode>>," in out


def test_counted_array_pointer_lifts_to_vec():
    arr = [Field("items", "Jval", None, True), Field("count", "int", None, False)]
    out = emit_safe_struct("JArray", arr, c_to_rust={"Jval": "Jval"})
    assert "pub items: alloc::vec::Vec<Jval>," in out
    assert "items: alloc::vec::Vec::new()" in out
    assert "pub count: i32," in out


def test_raw_buffer_pointer_still_dropped():
    """A raw scalar/char buffer pointer (no carried-struct pointee) has no faithful safe
    field and scalar offset logic doesn't observe it — rc4/allocators depend on this."""
    st = [Field("buf", "unsigned char", None, True), Field("pos", "int", None, False)]
    out = emit_safe_struct("St", st, c_to_rust={})
    assert "buf" not in out.split("pub ")[1] if "pub " in out else True
    assert "Box" not in out and "Vec" not in out
    assert "pub pos: i32," in out
    assert "dropped" in out  # the explanatory note


def test_pointer_lift_is_opt_in():
    """Without a c_to_rust map, behaviour is unchanged (pointers dropped) — so existing
    callers (rc4/sha256 struct-carry) can't regress."""
    node = [Field("val", "int", None, False), Field("next", "struct node", None, True)]
    out = emit_safe_struct("Node", node)
    assert "Box" not in out
    assert "pub val: i32," in out


# ---- transitive closure over a real linked-list source --------------------

def _p(name, rt):
    return Parameter(name=name, rust_type=rt, description="")


def test_inject_lifts_and_closes_over_linked_list(tmp_path: Path):
    src = tmp_path / "llist"
    src.mkdir()
    (src / "llist.c").write_text(
        "typedef struct node { int val; struct node *next; } node;\n"
        "int list_sum(node *head) {\n"
        "  int s = 0; node *p = head;\n"
        "  while (p) { s += p->val; p = p->next; }\n"
        "  return s;\n"
        "}\n"
    )
    # sanity: the struct + its self-pointer parsed
    structs = structs_in_dir(src)
    assert "node" in structs
    assert any(f.name == "next" and f.is_ptr for f in structs["node"])

    mod = ModuleSpec(
        name="llist", display_name="llist", description="",
        algorithms=[AlgorithmSpec(
            name="list_sum", display_name="list_sum", category="data_structure",
            description="", inputs=[_p("head", "&mut Node")])])
    n = inject_state_shared_types(str(src), [mod])
    assert n >= 1
    node_type = next((t for t in (mod.shared_types or []) if t.name == "Node"), None)
    assert node_type is not None, "Node state struct not emitted"
    assert "Option<alloc::boxed::Box<Node>>" in node_type.rust_definition, node_type.rust_definition
