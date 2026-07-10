"""Carried lookup tables must map C typedefs to Rust types. Lua's
`static const lu_byte log_2[256]` was emitted as `[lu_byte; 256]` — an undefined
Rust type (E0425) that blocked every table-carrying Lua fn (luaO_ceillog2)."""
from alchemist.extractor.constants_extractor import _rust_type_for, extract_constants


def test_lua_typedefs_resolve():
    assert _rust_type_for("lu_byte") == "u8"
    assert _rust_type_for("const lu_byte") == "u8"
    assert _rust_type_for("ls_byte") == "i8"
    assert _rust_type_for("lua_Integer") == "i64"
    assert _rust_type_for("lua_Number") == "f64"
    assert _rust_type_for("Instruction") == "u32"


def test_carried_lu_byte_table_uses_u8():
    src = (
        "typedef unsigned char lu_byte;\n"
        "int f(unsigned int x){\n"
        "  static const lu_byte log_2[4] = {0,1,2,2};\n"
        "  return log_2[x&3];\n}\n")
    consts = extract_constants(src, "f.c").extracted
    tbl = [c for c in consts if c.name == "log_2"]
    assert tbl, f"log_2 not extracted; got {[c.name for c in consts]}"
    assert "lu_byte" not in tbl[0].rust_type
    assert tbl[0].rust_type == "[u8; 4]"
