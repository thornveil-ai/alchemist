"""Regression: the architect must slim specs + budget its output reservation.

P4 (real converter run) hit HTTP 400 "input+output > max_model_len" because
crate_designer serialized FULL specs (test_vectors, mathematical_description —
7KB+ per fn) and reserved a fixed 16384 output tokens, overflowing the model
context on a tiny subject (and fatally so on a large library like Lua). These
tests lock in the slimming + that the design prompt stays small.
"""

from __future__ import annotations

import json

from alchemist.architect.crate_designer import _slim_module_for_design
from alchemist.extractor.schemas import (
    AlgorithmSpec, ModuleSpec, Parameter, StateVariable, TestVector,
)


def _heavy_module() -> ModuleSpec:
    vec = TestVector(description="x" * 4000, inputs={"input": 'b"a"'},
                     expected_output="0x1", tolerance="exact")
    alg = AlgorithmSpec(
        name="adler32", display_name="adler32", category="checksum",
        description="Adler-32 rolling checksum",
        mathematical_description="M" * 6000,
        inputs=[Parameter(name="data", rust_type="&[u8]", description="")],
        return_type="u32",
        state=[StateVariable(name="a", rust_type="u32", description="")],
        test_vectors=[vec] * 5,
        suggested_rust_traits=["Checksum"],
    )
    return ModuleSpec(name="tinychk", display_name="tinychk",
                      description="checksums", algorithms=[alg])


def test_slim_drops_heavy_fields_keeps_design_fields():
    mod = _heavy_module()
    slim = json.dumps(_slim_module_for_design(mod))
    full = json.dumps(mod.model_dump())
    # Dramatic shrink — the heavy fields are gone.
    assert len(slim) < len(full) // 5
    assert "test_vectors" not in slim
    assert "mathematical_description" not in slim
    # Design-relevant fields survive.
    assert "adler32" in slim and "Checksum" in slim
    assert "&[u8]" in slim and "u32" in slim
    assert '"name": "a"' in slim  # state var carried


def test_slim_module_shape():
    mod = _heavy_module()
    d = _slim_module_for_design(mod)
    assert set(d.keys()) == {"name", "description", "algorithms", "shared_types"}
    a = d["algorithms"][0]
    assert set(a.keys()) == {
        "name", "category", "description", "inputs", "return_type",
        "state", "suggested_rust_traits", "no_std_compatible", "unsafe_required",
    }
