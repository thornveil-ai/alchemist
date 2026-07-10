"""The repair loop must distill cargo's noisy left/right assertion dump into a
focused first-divergence hint, so the model can localize a subtle emission-order
bug instead of re-guessing the whole function. Uses the real smaz_compress
divergence (flush emitted after the code byte instead of before)."""

from __future__ import annotations

from alchemist.implementer.tdd_generator import _distill_vector_divergence


def test_distill_first_divergence_real_smaz_compress():
    # The exact left/right cargo emitted for test_smaz_compress_spec_8.
    out = (
        "thread 'x' panicked at smaz/src/smaz.rs:188:9:\n"
        "assertion `left == right` failed: transform_len_43\n"
        "  left: [72, 0, 38, 254, 113, 131, 94]\n"
        " right: [72, 0, 254, 113, 38, 131, 94]\n"
    )
    hint = _distill_vector_divergence(out)
    assert "index 2" in hint                      # first differing byte is index 2
    assert "you emitted 38, C emitted 254" in hint
    # these vectors are a pure reordering -> sharp emission-order instruction
    assert "EMISSION-ORDER" in hint
    assert "38" in hint


def test_distill_permutation_gives_sharp_ordering_instruction():
    # Same bytes, reordered => must give the unambiguous "flush pending output
    # BEFORE the new token" instruction (the smaz_compress flush-order case).
    out = (
        "  left: [109, 255, 5, 113, 204]\n"
        " right: [255, 5, 113, 204, 109]\n"
    )
    hint = _distill_vector_divergence(out)
    assert "EXACT SAME bytes" in hint
    assert "EMISSION-ORDER" in hint
    assert "FIRST emit" in hint or "BEFORE" in hint


def test_distill_length_mismatch():
    out = "  left: [1, 2, 3]\n right: [1, 2, 3, 4, 5]\n"
    hint = _distill_vector_divergence(out)
    assert "index 3" in hint
    assert "ends early" in hint


def test_distill_no_pair_returns_empty():
    assert _distill_vector_divergence("compile error: mismatched types") == ""
    assert _distill_vector_divergence("") == ""


def test_distill_identical_returns_empty():
    assert _distill_vector_divergence("left: [1, 2, 3]\nright: [1, 2, 3]") == ""
