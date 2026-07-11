"""P0.2/P0.8 — the generated KAT/fuzz-vector test must call the function in its
SIGNATURE argument order, not the fuzz-vector's dict order.

The deepest false-refusal found this session: for adler32 (signature `(seed, buf)`)
the fuzz vector's inputs were built `{buf, seed}`, so _emit_spec_test emitted
`super::adler32(buf, seed)` — a swapped-argument call that can't compile. The
model's byte-exact-correct adler32 was refused forever, no matter how it retried.
The call must be ordered by the function signature.
"""

from __future__ import annotations

from alchemist.extractor.schemas import AlgorithmSpec, Parameter
from alchemist.implementer.test_generator import _emit_spec_test, SpecTestVector


def _adler_alg():
    return AlgorithmSpec(
        name="adler32", display_name="adler32", category="checksum", description="",
        inputs=[Parameter(name="seed", rust_type="u32", description=""),
                Parameter(name="buf", rust_type="&[u8]", description="")],
        return_type="u32",
    )


def test_call_ordered_by_signature_not_vector_dict():
    # Vector inputs in the WRONG (reversed) order relative to the signature.
    vec = SpecTestVector(inputs={"buf": "&[0x00]", "seed": "1u32"},
                         expected_output="65537", tolerance="exact",
                         description="fuzz_input_len_1")
    out = _emit_spec_test("adler32", vec, 1, return_type="u32", alg=_adler_alg())
    assert "super::adler32(seed, buf)" in out, "call must be in signature order"
    assert "super::adler32(buf, seed)" not in out
    # Bindings + expected value survive.
    assert "let buf = &[0x00];" in out
    assert "let seed = 1u32;" in out
    assert "65537" in out


def test_falls_back_to_vector_order_without_alg():
    # No alg provided → keep vector order (prior behavior; no crash).
    vec = SpecTestVector(inputs={"buf": "&[0x00]", "seed": "1u32"},
                         expected_output="65537", tolerance="exact", description="v")
    out = _emit_spec_test("adler32", vec, 1, return_type="u32")
    assert "super::adler32(buf, seed)" in out


def test_matching_order_is_unchanged():
    # Vector already in signature order → identical output.
    vec = SpecTestVector(inputs={"seed": "1u32", "buf": "&[0x00]"},
                         expected_output="65537", tolerance="exact", description="v")
    out = _emit_spec_test("adler32", vec, 1, return_type="u32", alg=_adler_alg())
    assert "super::adler32(seed, buf)" in out
