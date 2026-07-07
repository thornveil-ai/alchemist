"""Pillar 2 — whole-program type model: consistent types + bottom-up order."""

from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.type_model import ProgramTypeModel


def test_same_struct_resolves_identically_across_functions():
    # a ctx produced by one fn and consumed by another must be the SAME Rust type
    src = ("typedef struct { int x; } SHA256_CTX;\n"
           "void sha256_init(SHA256_CTX *c);\n"
           "void sha256_final(SHA256_CTX *c, BYTE out[]);\n")
    m = ProgramTypeModel.from_sources([src])
    assert m.is_struct("SHA256_CTX")
    assert m.rust_type("SHA256_CTX *") == "&mut Sha256Ctx"
    assert m.rust_type("const SHA256_CTX *") == "&Sha256Ctx"   # const -> shared borrow


def test_coherent_role_rewrites():
    m = ProgramTypeModel.from_sources([""])
    assert m.rust_type("const BYTE *", role="buffer") == "&[u8]"      # (ptr,len) -> slice
    assert m.rust_type("BYTE *", role="out_buffer") == "Vec<u8>"      # out -> owned return
    assert m.rust_type("unsigned long") == "u64"
    assert m.rust_type("int") == "i32"


def test_topo_order_is_leaves_first():
    src = ("int leaf(int x) {\n    return x + 1;\n}\n"
           "int mid(int x) {\n    return leaf(x) + 1;\n}\n"
           "int top(int x) {\n    return mid(x) + leaf(x);\n}\n")
    funcs = discover_functions(src)
    order = ProgramTypeModel.from_sources([src]).topo_order(funcs)
    assert order.index("leaf") < order.index("mid") < order.index("top")


def test_topo_order_tolerates_recursion():
    src = ("int a(int x) {\n    return b(x);\n}\n"
           "int b(int x) {\n    return a(x);\n}\n")   # mutual recursion -> no deadlock
    funcs = discover_functions(src)
    order = ProgramTypeModel.from_sources([src]).topo_order(funcs)
    assert set(order) == {"a", "b"}
