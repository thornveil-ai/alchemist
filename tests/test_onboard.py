"""Auto-onboarding: table extraction, function discovery, call-graph fill order.

The two things real-world C (ArduPilot crc.cpp) broke that clean subjects didn't:
extract EVERY table (not a subset) and fill in dependency order.
"""

from alchemist.autonomy.onboard import (
    extract_tables, discover_functions, fill_order, c_to_rust_scalar, CTable,
    extract_char_defines,
)

CRC_LIKE = r"""
#include <stdint.h>

static const uint8_t crc8_table[] = {
    0x00, 0x07, 0x0e, 0x09,
};
/* '0','1','2','3' ASCII rows 48 49 50 51 — comment numbers must NOT leak */
static const uint16_t crc16tab[256] = { 1, 2, 3 };
static const uint32_t crc32_tab[] = { 100, 200 };

uint16_t crc_xmodem_update(uint16_t crc, uint8_t data) {
    crc = crc ^ ((uint16_t)data << 8);
    return crc;
}

uint16_t crc_xmodem(const uint8_t *data, uint16_t len) {
    uint16_t crc = 0;
    for (uint16_t i = 0; i < len; i++) {
        crc = crc_xmodem_update(crc, data[i]);
    }
    return crc;
}

uint8_t crc_crc8(const uint8_t *p, uint8_t len) {
    uint8_t crc = 0;
    while (len--) { crc = crc8_table[crc ^ *p++]; }
    return crc;
}
"""


def test_extracts_every_table():
    tabs = extract_tables(CRC_LIKE)
    assert set(tabs) == {"crc8_table", "crc16tab", "crc32_tab"}
    assert tabs["crc8_table"].rust_type == "u8"
    assert tabs["crc16tab"].rust_type == "u16"
    assert tabs["crc32_tab"].rust_type == "u32"


def test_comment_numbers_do_not_leak():
    # the "48 49 50 51" live in a comment between tables — must not appear as values
    tabs = extract_tables(CRC_LIKE)
    assert tabs["crc16tab"].values == [1, 2, 3]
    assert 48 not in tabs["crc16tab"].values


def test_table_rust_const_render():
    t = CTable("crc8_table", "u8", [0, 7, 14])
    assert t.rust_const() == "pub const CRC8_TABLE: [u8; 3] = [0, 7, 14];"


def test_discovers_functions_and_calls():
    funcs = discover_functions(CRC_LIKE)
    assert set(funcs) == {"crc_xmodem_update", "crc_xmodem", "crc_crc8"}
    assert funcs["crc_xmodem"].calls == {"crc_xmodem_update"}
    assert funcs["crc_crc8"].calls == set()  # crc8_table is data, not a function


def test_control_keywords_are_not_functions():
    funcs = discover_functions(CRC_LIKE)
    for kw in ("if", "for", "while", "return"):
        assert kw not in funcs


def test_fill_order_puts_helper_before_caller():
    funcs = discover_functions(CRC_LIKE)
    order = fill_order(funcs)
    assert order.index("crc_xmodem_update") < order.index("crc_xmodem")
    assert set(order) == set(funcs)


def test_fill_order_tolerates_cycles():
    # mutually-recursive C should not crash; every fn still appears once
    src = """
    int a(int x) { return b(x); }
    int b(int x) { return a(x); }
    """
    funcs = discover_functions(src)
    order = fill_order(funcs)
    assert set(order) == {"a", "b"}


def test_char_literal_table():
    src = "static const char b64en[] = { 'A', 'B', 'C', '+', '/' };"
    tabs = extract_tables(src)
    assert tabs["b64en"].values == [65, 66, 67, 43, 47]


def test_kandr_multiline_function_definition():
    # return type on its own line (base64.c style)
    src = (
        "unsigned int\n"
        "base64_encode(const unsigned char *in, unsigned int inlen, char *out)\n"
        "{\n    return 0;\n}\n"
    )
    funcs = discover_functions(src)
    assert "base64_encode" in funcs
    assert funcs["base64_encode"].ret.replace(" ", "") == "unsignedint"


def test_extract_char_defines():
    src = "#define BASE64_PAD '='\n#define FIRST '+'\n#define NL '\\n'\n#define NOTACHAR 42\n"
    d = extract_char_defines(src)
    assert d == {"BASE64_PAD": 61, "FIRST": 43, "NL": 10}  # integer #define excluded


def test_c_to_rust_scalar():
    assert c_to_rust_scalar("uint8_t") == "u8"
    assert c_to_rust_scalar("unsigned int") == "u32"
    assert c_to_rust_scalar("const uint32_t") == "u32"
