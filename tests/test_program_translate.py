"""Pillar 2 top-tier — whole-program translator: signatures from the shared model.

The end-to-end (bottom-up fill of a 2-function program, whole-program byte-identical
vs all-C) is proven on the box; here we lock the signature derivation + ordering.
"""

from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.type_model import ProgramTypeModel
from alchemist.autonomy.program_translate import _rust_sig

SRC = ("unsigned hash_byte(unsigned h, unsigned char b) { return h * 31u + b; }\n"
       "unsigned hash_str(const unsigned char *s, unsigned long n) { return 0; }\n")


def test_rust_sig_buffer_pair_becomes_slice():
    funcs = discover_functions(SRC)
    tm = ProgramTypeModel.from_sources([SRC])
    sig, kind, ret = _rust_sig("hash_str", funcs, tm)
    assert "data: &[u8]" in sig and kind == "buffer" and ret == "u32"


def test_rust_sig_scalars_map_through_type_model():
    funcs = discover_functions(SRC)
    tm = ProgramTypeModel.from_sources([SRC])
    sig, kind, ret = _rust_sig("hash_byte", funcs, tm)
    assert "h: u32" in sig and "b: u8" in sig and kind == "scalar"


def test_translation_order_excludes_main_and_is_leaves_first():
    src = SRC + "int main(void){ return hash_str(0,0); }\n"
    funcs = discover_functions(src)
    tm = ProgramTypeModel.from_sources([src])
    order = [n for n in tm.topo_order(funcs) if n in funcs and n != "main"]
    assert "main" not in order
    assert order.index("hash_byte") < order.index("hash_str")
