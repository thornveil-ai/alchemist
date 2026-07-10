"""Carried lookup tables must map C typedefs to Rust types. Lua's
`static const lu_byte log_2[256]` was emitted as `[lu_byte; 256]` — an undefined
Rust type (E0425) that blocked every table-carrying Lua fn (luaO_ceillog2).

The resolution is GENERAL: aliases are learned from the subject's OWN
`typedef` / scalar type-macro declarations (build_typedef_map), never a
hardcoded per-library table. Genuine C primitives still map with no map."""
from alchemist.extractor.constants_extractor import (
    _rust_type_for, extract_constants, build_typedef_map,
)

# Lua's own scalar-type declarations (llimits.h / luaconf.h). These are the
# SOURCE the harness reads — not a curated table inside Alchemist.
_LUA_TYPE_DECLS = """
typedef unsigned char lu_byte;
typedef signed char ls_byte;
typedef unsigned int Instruction;
#define LUAI_UACINT long long
#define LUAI_UACNUMBER double
typedef LUAI_UACINT lua_Integer;
typedef LUAI_UACNUMBER lua_Number;
"""


def test_lua_typedefs_resolve_from_source():
    tm = build_typedef_map([_LUA_TYPE_DECLS])
    assert _rust_type_for("lu_byte", tm) == "u8"
    assert _rust_type_for("const lu_byte", tm) == "u8"
    assert _rust_type_for("ls_byte", tm) == "i8"
    assert _rust_type_for("lua_Integer", tm) == "i64"   # chains through macro
    assert _rust_type_for("lua_Number", tm) == "f64"    # chains through macro
    assert _rust_type_for("Instruction", tm) == "u32"


def test_c_primitives_resolve_without_a_map():
    # Genuine C-language primitives are universal, not codebase-specific.
    assert _rust_type_for("unsigned char") == "u8"
    assert _rust_type_for("unsigned int") == "u32"
    assert _rust_type_for("long long") == "i64"
    assert _rust_type_for("size_t") == "usize"
    assert _rust_type_for("double") == "f64"


def test_unknown_alias_passes_through_without_source():
    # With NO typedef map, a codebase-specific alias is unresolved (not faked).
    assert _rust_type_for("lu_byte") == "lu_byte"
    assert _rust_type_for("Bytef") == "Bytef"


def test_carried_lu_byte_table_uses_u8():
    # Self-contained file: the typedef lives in the same unit, so extract_constants
    # self-scans it and resolves the carried table with no caller-supplied map.
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


def test_cross_header_typedef_map_resolves_table():
    # Realistic split: typedef in a header string, table in a source string.
    header = "typedef unsigned char lu_byte;\n"
    src = "static const lu_byte log_2[4] = {0,1,2,2};\n"
    tm = build_typedef_map([header])
    consts = extract_constants(src, "f.c", typedef_map=tm).extracted
    tbl = [c for c in consts if c.name == "log_2"]
    assert tbl and tbl[0].rust_type == "[u8; 4]"


def test_type_alias_macro_not_emitted_as_value_const():
    # `#define LUAI_UACINT long long` is a type alias, not a value constant.
    consts = extract_constants(_LUA_TYPE_DECLS, "conf.c").extracted
    assert not any(c.name == "LUAI_UACINT" for c in consts)
    assert not any(c.name == "LUAI_UACNUMBER" for c in consts)
