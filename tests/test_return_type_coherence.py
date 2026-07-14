"""Whole-program type coherence for SIGNATURE types (extends keystone #1 from state-carry
to the full type universe). parson's skeleton failed to compile (E0425) on its DOM types:

  1. `typedef struct json_value_t JSON_Value;` — an OPAQUE/forward typedef (struct declared
     separately, no inline body). Only the tag was keyed, so `JSON_Value*` params/returns
     were UNKNOWN types → never emitted.
  2. A struct that appears ONLY as a RETURN type (`JSON_Value* json_parse_string(...)`) was
     invisible to the param-only canonicalization → never emitted.
  3. The same C type got two Rust names across functions (`JsonValue` vs `JSONValue`).
  4. The tag (`json_value_t`, used in the self-ref field `*parent`) and the alias
     (`JSON_Value`, used in signatures) must share ONE canonical name or the self-ref field
     references a different type than the signatures.

Driven with a synthetic parson-shaped source (no model needed).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from alchemist.verifier.struct_lift import (
    inject_state_shared_types,
    structs_in_dir,
    collect_struct_typedefs,
)
from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec, Parameter

_SRC = """
struct json_value_t { int type; struct json_value_t *parent; };
struct json_object_t { int count; int cap; };
typedef struct json_value_t JSON_Value;
typedef struct json_object_t JSON_Object;
JSON_Value *json_parse_string(const char *s) { (void)s; return 0; }
JSON_Value *json_object_get_value(const JSON_Object *o, const char *n) { (void)o;(void)n; return 0; }
"""


def _subject():
    d = Path(tempfile.mkdtemp())
    (d / "parson.c").write_text(_SRC)
    return d


def _p(n, t):
    return Parameter(name=n, rust_type=t, description="")


def _module():
    return ModuleSpec(name="parson", display_name="parson", description="", algorithms=[
        AlgorithmSpec(name="json_parse_string", display_name="x", category="data_structure",
                      description="", inputs=[_p("s", "&str")], return_type="Option<JsonValue>"),
        AlgorithmSpec(name="json_object_get_value", display_name="x", category="data_structure",
                      description="", inputs=[_p("o", "&JsonObject"), _p("n", "&str")],
                      return_type="Option<&JSONValue>"),  # inconsistent name for same C type
    ])


def test_opaque_typedef_aliases_are_keyed():
    d = _subject()
    assert collect_struct_typedefs(d) == {"JSON_Value": "json_value_t", "JSON_Object": "json_object_t"}
    S = structs_in_dir(d)
    assert "JSON_Value" in S and "JSON_Object" in S      # aliases resolve to the tag's fields
    assert S["JSON_Value"] is S["json_value_t"]


def test_return_only_and_param_structs_both_emitted():
    d, mod = _subject(), _module()
    inject_state_shared_types(str(d), [mod])
    emitted = sorted(t.name for t in (mod.shared_types or []))
    assert "JsonValue" in emitted        # return-only struct
    assert "JsonObject" in emitted        # param struct


def test_return_type_name_canonicalized():
    d, mod = _subject(), _module()
    inject_state_shared_types(str(d), [mod])
    rets = [a.return_type for a in mod.algorithms]
    assert all("JSONValue" not in r for r in rets)       # -> JsonValue everywhere
    assert "Option<JsonValue>" in rets and "Option<&JsonValue>" in rets


def test_tag_alias_unified_no_duplicate_type():
    d, mod = _subject(), _module()
    inject_state_shared_types(str(d), [mod])
    emitted = [t.name for t in mod.shared_types]
    defs = "\n".join(t.rust_definition for t in mod.shared_types)
    assert "JsonValueT" not in emitted and "JsonValueT" not in defs   # tag not a 2nd type
    assert "Option<Box<JsonValue>>" in defs   # self-ref parent -> canonical, not JsonValueT
