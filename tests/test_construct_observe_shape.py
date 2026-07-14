"""Tagged-union DOM oracle (P1, parson): pair scalar constructors with scalar observers
and verify the construct->observe PAIR as one differential unit. This lets a tagged-union
DOM library get a real verified core (constructors + scalar getters) despite every function
needing a tree value that can't be shared across the C/Rust ABI boundary."""

from __future__ import annotations

from pathlib import Path

from alchemist.verifier.auto_config import (
    classify_construct_observe,
    collect_subject_signatures,
)
from alchemist.verifier import struct_lift as sl
from alchemist.implementer.test_generator import _emit_construct_observe_test
from alchemist.extractor.schemas import TestVector


_PARSON_C = """
typedef int JSON_Value_Type;
typedef struct json_string_t { char *chars; size_t length; } JSON_String;
typedef struct json_object_t JSON_Object;
typedef struct json_array_t JSON_Array;
typedef struct json_value_t JSON_Value;
typedef union json_value_value {
    JSON_String  string; double number; JSON_Object *object;
    JSON_Array  *array; int boolean; int null;
} JSON_Value_Value;
struct json_object_t { JSON_Value *wrapping_value; size_t count; };
struct json_array_t { JSON_Value *wrapping_value; size_t count; };
struct json_value_t { JSON_Value *parent; JSON_Value_Type type; JSON_Value_Value value; };

JSON_Value * json_value_init_null(void) { return 0; }
JSON_Value * json_value_init_number(double n) { return 0; }
JSON_Value * json_value_init_boolean(int b) { return 0; }
double json_value_get_number(const JSON_Value *value) { return value->value.number; }
int json_value_get_type(const JSON_Value *value) { return value->type; }
int json_value_get_boolean(const JSON_Value *value) { return value->value.boolean; }
"""


class _I:
    def __init__(self, n, rt):
        self.name, self.rust_type = n, rt


class _A:
    def __init__(self, n, inputs, ret):
        self.name, self.inputs, self.return_type, self.outputs = n, inputs, ret, []


class _M:
    def __init__(self, algs):
        self.algorithms = algs


def _specs():
    return [_M([
        _A("json_value_init_null", [], "Option<JsonValue>"),
        _A("json_value_init_number", [_I("n", "f64")], "Option<JsonValue>"),
        _A("json_value_init_boolean", [_I("b", "bool")], "Option<JsonValue>"),
        _A("json_value_get_number", [_I("value", "&JsonValue")], "f64"),
        _A("json_value_get_type", [_I("value", "Option<&JsonValue>")], "i32"),
        _A("json_value_get_boolean", [_I("value", "&JsonValue")], "Option<bool>"),
    ])]


def _classify(tmp_path):
    (tmp_path / "parson.c").write_text(_PARSON_C, encoding="utf-8")
    sigs = {s.name: s for s in collect_subject_signatures(str(tmp_path))}
    structs = sl.structs_in_dir(str(tmp_path))
    return classify_construct_observe(sigs, structs, _specs())


def test_classify_finds_ctors_and_scalar_observers(tmp_path):
    g = _classify(tmp_path)
    assert g is not None
    assert g["rust"] == "JsonValue"
    ctors = {c[0] for c in g["constructors"]}
    obs = {o[0] for o in g["observers"]}
    assert {"json_value_init_null", "json_value_init_number", "json_value_init_boolean"} <= ctors
    # numeric-return observers included; Option<bool> observer excluded (Tier-2)
    assert {"json_value_get_number", "json_value_get_type"} <= obs
    assert "json_value_get_boolean" not in obs


def test_emit_float_observer_uses_bit_exact_compare():
    v = TestVector(
        description="co_x", source="s",
        inputs={"__seed__": "f64::from_bits(1u64)", "__obs__": "json_value_get_number"},
        expected_output="4614256650576692846",
        tolerance="construct_observe|JsonValue|json_value_init_number|opt|f64|ref|f",
    )
    out = _emit_construct_observe_test("json_value_get_number", v, 0)
    assert "super::json_value_init_number(f64::from_bits(1u64))" in out
    assert "v.as_ref().expect" in out          # Option<JsonValue> -> &JsonValue
    assert "out.to_bits()" in out              # bit-exact float compare
    assert "4614256650576692846u64" in out


def test_emit_int_observer_opt_ref_input():
    v = TestVector(
        description="co_y", source="s",
        inputs={"__seed__": "", "__obs__": "json_value_get_type"},
        expected_output="1",
        tolerance="construct_observe|JsonValue|json_value_init_null|opt|i32|opt_ref|i",
    )
    out = _emit_construct_observe_test("json_value_init_null", v, 0)
    assert "super::json_value_init_null()" in out
    assert "Some(v.as_ref().expect" in out     # Option<&JsonValue> input
    assert "out as i64, 1i64" in out
