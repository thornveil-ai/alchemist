"""Tagged-union DOM keystone (P1): an inline C union field (parson's
`JSON_Value_Value value;`) is LIFTED to a flattened safe Rust sub-struct — one
field per union member — instead of being dropped. The Rust access path
`v.value.number` then matches the C `v->value.number` exactly, so a tagged-union
library's constructors / scalar getters can verify byte-exact. Fully safe (no
`union`, no `unsafe`)."""

from __future__ import annotations

from pathlib import Path

from alchemist.verifier.struct_lift import (
    collect_union_typedefs,
    inject_state_shared_types,
)


_PARSON_C = """
typedef int JSON_Value_Type;
typedef struct json_string_t { char *chars; size_t length; } JSON_String;
typedef struct json_object_t JSON_Object;
typedef struct json_array_t JSON_Array;
typedef struct json_value_t JSON_Value;
typedef union json_value_value {
    JSON_String  string;
    double       number;
    JSON_Object *object;
    JSON_Array  *array;
    int          boolean;
    int          null;
} JSON_Value_Value;
struct json_object_t { JSON_Value *wrapping_value; size_t count; };
struct json_array_t { JSON_Value *wrapping_value; size_t count; };
struct json_value_t { JSON_Value *parent; JSON_Value_Type type; JSON_Value_Value value; };

JSON_Value * json_value_init_boolean(int boolean) { JSON_Value *v = 0; return v; }
double json_value_get_number(const JSON_Value *value) { return value->value.number; }
int json_value_get_boolean(const JSON_Value *value) { return value->value.boolean; }
"""


class _I:
    def __init__(self, n, rt):
        self.name = n
        self.rust_type = rt


class _A:
    def __init__(self, n, inputs, ret):
        self.name = n
        self.inputs = inputs
        self.return_type = ret
        self.outputs = []


class _M:
    def __init__(self, algs):
        self.algorithms = algs
        self.shared_types = []


def _subject(tmp_path: Path) -> str:
    (tmp_path / "parson.c").write_text(_PARSON_C, encoding="utf-8")
    return str(tmp_path)


def test_collect_union_typedefs_members():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        Path(d, "parson.c").write_text(_PARSON_C, encoding="utf-8")
        u = collect_union_typedefs(d)
    # keyed by both alias and tag
    assert "JSON_Value_Value" in u and "json_value_value" in u
    names = {f.name for f in u["JSON_Value_Value"]}
    assert {"string", "number", "object", "array", "boolean", "null"} <= names
    by = {f.name: f for f in u["JSON_Value_Value"]}
    assert by["number"].ctype == "double" and not by["number"].is_ptr
    assert by["object"].is_ptr and by["array"].is_ptr


def test_union_field_flattened_into_carried_struct(tmp_path):
    specs = [_M([
        _A("json_value_init_boolean", [_I("boolean", "bool")], "Option<JSONValue>"),
        _A("json_value_get_number", [_I("value", "&JsonValue")], "f64"),
        _A("json_value_get_boolean", [_I("value", "&JsonValue")], "Option<bool>"),
    ])]
    n = inject_state_shared_types(_subject(tmp_path), specs)
    assert n >= 2
    by_name = {t.name: t.rust_definition for t in specs[0].shared_types}

    # JsonValue carries the union as a flattened sub-struct field (not dropped).
    assert "JsonValue" in by_name
    assert "pub value: JsonValueValue," in by_name["JsonValue"]

    # The flattened union sub-struct exposes the SCALAR members concretely so
    # get_number / get_boolean can observe them.
    assert "JsonValueValue" in by_name
    jvv = by_name["JsonValueValue"]
    assert "pub number: f64," in jvv
    assert "pub boolean: i32," in jvv
    assert "pub null: i32," in jvv
    # container members lifted to owned Box (transitive closure emits them)
    assert "pub object: Option<alloc::boxed::Box<JsonObject>>," in jvv
    assert "JsonObject" in by_name and "JsonArray" in by_name
    # the lift is a plain safe struct — no Rust `union` keyword, no `unsafe`
    # (the word "union" appears only in the dropped-field explanatory comment)
    assert "pub struct JsonValueValue {" in jvv
    assert "pub union" not in jvv
    assert "unsafe" not in jvv


def test_casing_coherence_constructor_return(tmp_path):
    # The extractor idiomatized the constructor return as `Option<JSONValue>` while
    # getters use `JsonValue`; whole-program canonicalization must unify them so the
    # constructor's result can chain into the getters (the construct-observe oracle).
    specs = [_M([
        _A("json_value_init_boolean", [_I("boolean", "bool")], "Option<JSONValue>"),
        _A("json_value_get_number", [_I("value", "&JsonValue")], "f64"),
        _A("json_value_get_boolean", [_I("value", "&JsonValue")], "Option<bool>"),
    ])]
    inject_state_shared_types(_subject(tmp_path), specs)
    assert specs[0].algorithms[0].return_type == "Option<JsonValue>"
