"""P1 struct-carry: resolve the library's own scalar typedefs (BYTE/WORD/…).

Found on sha256: `typedef unsigned char BYTE; typedef unsigned int WORD;` with a
state struct `SHA256_CTX { BYTE data[64]; WORD state[8]; ... }`. Because BYTE/WORD
didn't resolve to a Rust scalar, emit_safe_struct returned None -> the state
struct was never carried -> the skeleton hit `cannot find type Sha256Context`
-> 0 functions filled -> the WHOLE library failed. Real C libraries define these
integer aliases constantly, so this blocked a large class of libraries.
"""

from __future__ import annotations

from pathlib import Path

from alchemist.verifier.struct_lift import (
    collect_scalar_typedefs,
    collect_enum_typedefs,
    structs_in_dir,
    emit_safe_struct,
)


def _write(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def test_collect_scalar_typedefs(tmp_path):
    _write(tmp_path, "types.h",
           "typedef unsigned char BYTE;\n"
           "typedef unsigned int WORD;\n"
           "typedef WORD DWORD;\n"          # typedef of a typedef (transitive)
           "typedef struct { int x; } NotScalar;\n")  # struct typedef -> skipped
    td = collect_scalar_typedefs(tmp_path)
    assert td["BYTE"] == "unsigned char"
    assert td["WORD"] == "unsigned int"
    assert td["DWORD"] == "unsigned int"     # resolved through WORD
    assert "NotScalar" not in td             # non-scalar typedefs excluded


def test_struct_fields_resolve_typedefs(tmp_path):
    _write(tmp_path, "sha256.h",
           "typedef unsigned char BYTE;\n"
           "typedef unsigned int  WORD;\n"
           "typedef struct {\n"
           "  BYTE data[64];\n"
           "  WORD datalen;\n"
           "  unsigned long long bitlen;\n"
           "  WORD state[8];\n"
           "} SHA256_CTX;\n")
    structs = structs_in_dir(tmp_path)
    assert "SHA256_CTX" in structs
    # every field ctype is now a real scalar (typedef aliases resolved)
    types = {f.name: f.ctype for f in structs["SHA256_CTX"]}
    assert types["data"] == "unsigned char"
    assert types["state"] == "unsigned int"
    # and the safe struct now emits (previously returned None -> struct never carried)
    out = emit_safe_struct("Sha256Context", structs["SHA256_CTX"])
    assert out is not None
    assert "pub data: [u8; 64]" in out
    assert "pub state: [u32; 8]" in out
    assert "pub datalen: u32" in out
    assert "pub bitlen: u64" in out
    assert "impl Default for Sha256Context" in out


def test_enum_typedef_and_ifdef_and_keyword_field(tmp_path):
    """jsmn: a token struct with an enum-typedef field (`jsmntype_t type;`), a
    preprocessor-conditional field (`#ifdef JSMN_PARENT_LINKS int parent;`), and a
    field named `type` (a Rust keyword). All three previously broke struct-carry."""
    _write(tmp_path, "jsmn.h",
           "typedef enum { JSMN_UNDEFINED = 0, JSMN_OBJECT = 1 } jsmntype_t;\n"
           "typedef struct jsmntok {\n"
           "    jsmntype_t type;\n"
           "    int start;\n"
           "    int end;\n"
           "    int size;\n"
           "#ifdef JSMN_PARENT_LINKS\n"
           "    int parent;\n"
           "#endif\n"
           "} jsmntok_t;\n")
    assert collect_enum_typedefs(tmp_path) == {"jsmntype_t": "int"}
    structs = structs_in_dir(tmp_path)
    tok = structs.get("jsmntok_t") or structs.get("jsmntok")
    types = {f.name: f.ctype for f in tok}
    assert types["type"] == "int"          # enum typedef resolved
    assert types["parent"] == "int"        # #ifdef stripped, field kept
    out = emit_safe_struct("JsmnTok", tok)
    assert out is not None
    assert "pub r#type: i32" in out        # Rust keyword escaped
    assert "pub parent: i32" in out
    assert "r#type: 0" in out              # ...in the Default impl too
