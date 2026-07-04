"""pqdownheap state-mutator: emitter borrows the tree slice arg correctly."""
from alchemist.extractor.schemas import TestVector as V
from alchemist.implementer.test_generator import _emit_state_mutator_test


def _pq_vec():
    return V(
        description="pqdownheap_shim_0",
        source="C reference via shim: shim_run_pqdownheap",
        inputs={
            "state.heap": "vec![0i32, 5i32, 3i32]",
            "state.heap_len": "2i32",
            "state.depth": "vec![0u8, 1u8]",
            "tree": "vec![zlib_types::TreeElement { freq: 10u16, ..Default::default() }]",
            "k": "1usize",
        },
        expected_output="heap:Vec<i32>=vec![0i32, 3i32, 5i32]",
        tolerance="state_mutator",
    )


def test_pqdownheap_emitter_borrows_tree_passes_scalar():
    out = _emit_state_mutator_test("pqdownheap", _pq_vec(), 0)
    # tree (a Vec) is borrowed; k (scalar) passed by value
    assert "super::pqdownheap(&mut state, &tree, k);" in out
    assert "let tree = vec![" in out
    assert "let k = 1usize;" in out
    assert "state.heap = vec![0i32, 5i32, 3i32];" in out
    assert 'assert_eq!(state.heap,' in out


def test_scalar_only_mutator_not_borrowed():
    """A scalar extra arg must still pass by value (regression guard)."""
    v = V(description="d", source="s",
          inputs={"state.bi_buf": "5u16", "value": "3i32", "length": "7u8"},
          expected_output="bi_buf:u16=8u16", tolerance="state_mutator")
    out = _emit_state_mutator_test("send_bits", v, 0)
    assert "super::send_bits(&mut state, value, length);" in out  # no & prefix


def test_rust_body_emitter_wraps_authored_body():
    from alchemist.extractor.schemas import TestVector as V
    from alchemist.implementer.test_generator import _emit_spec_test
    body = "let mut tree = vec![];\nsuper::gen_codes(&mut tree, 0usize, &[]);\nassert_eq!(1, 1, \"x\");"
    v = V(description="d", source="s", inputs={}, expected_output=body, tolerance="rust_body")
    out = _emit_spec_test("gen_codes", v, 3)
    assert "fn test_gen_codes_body_3()" in out
    assert "super::gen_codes(&mut tree, 0usize, &[]);" in out
    assert out.count("#[test]") == 1
