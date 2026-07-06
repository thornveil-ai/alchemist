"""Tests for the general C-struct field parser (library-agnostic WS1)."""

from alchemist.autonomy.c_struct import parse_struct_fields


def test_tagged_struct():
    src = "struct point { int x; unsigned long y; char *label; };"
    f = parse_struct_fields(src, "point")
    assert f == {"x": "int", "y": "unsigned long", "label": "char"}


def test_typedef_alias_struct():
    src = """
    typedef struct internal_s {
        int   status;      /* the status; braces { } in a comment */
        uInt  w_size;      /* window size */
        Bytef *window;
        ulg   pending;
    } FAR my_state;
    """
    f = parse_struct_fields(src, "my_state")
    assert f["status"] == "int"
    assert f["w_size"] == "uInt"
    assert f["window"] == "Bytef"
    assert f["pending"] == "ulg"
    # comment text must NOT leak into a field type
    assert "comment" not in " ".join(f.values())


def test_arrays_stripped():
    src = "typedef struct { int heap[600]; unsigned char depth[1146]; } S;"
    f = parse_struct_fields(src, "S")
    assert f["heap"] == "int"
    assert f["depth"] == "unsigned char"


def test_comma_declarators_share_type():
    src = "struct v { int a, b, c; };"
    f = parse_struct_fields(src, "v")
    assert f["a"] == "int" and f["b"] == "int" and f["c"] == "int"


def test_missing_struct_returns_empty():
    assert parse_struct_fields("struct other { int x; };", "nope") == {}


def test_nested_inline_group_skipped_not_crashed():
    # inline union shouldn't crash the parser; scalar fields still parse
    src = "typedef struct { int tag; union { int a; long b; } u; short s; } W;"
    f = parse_struct_fields(src, "W")
    assert f["tag"] == "int"
    assert f["s"] == "short"
