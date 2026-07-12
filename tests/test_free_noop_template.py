"""P1: a pure `void free_X(ptr)` (C body only deallocation) is a no-op in safe Rust
(owned Vec/Box drops automatically). Accept it — body-confirmed, so fail-closed:
any other statement in the body defers to the model. Clears heap:free_buffer's
"no test vectors" refusal."""

from __future__ import annotations

from pathlib import Path

from alchemist.extractor.schemas import AlgorithmSpec, Parameter
from alchemist.implementer.init_templates import free_noop_template


def _alg(name, ret, ins):
    return AlgorithmSpec(name=name, display_name=name, category="utility",
                         description="d", return_type=ret, inputs=ins)


def _buf():
    return [Parameter(name="p", rust_type="Vec<u8>", description="p")]


def test_pure_free_accepted(tmp_path):
    (tmp_path / "heap.c").write_text(
        "#include <stdlib.h>\nvoid free_buffer(unsigned char *p) { free(p); }\n",
        encoding="utf-8")
    out = free_noop_template(_alg("free_buffer", "()", _buf()), tmp_path)
    assert out is not None
    assert "pub fn free_buffer(p: Vec<u8>)" in out
    assert "unimplemented" not in out          # a real (empty) body, not a stub


def test_impure_body_rejected(tmp_path):
    # a "cleanup" that also does real work must NOT be accepted as a no-op
    (tmp_path / "x.c").write_text(
        "void cleanup(unsigned char *p) { g_counter--; free(p); }\n", encoding="utf-8")
    assert free_noop_template(_alg("cleanup", "()", _buf()), tmp_path) is None


def test_non_void_rejected(tmp_path):
    (tmp_path / "y.c").write_text(
        "int take(unsigned char *p) { free(p); return 0; }\n", encoding="utf-8")
    assert free_noop_template(_alg("take", "i32", _buf()), tmp_path) is None


def test_no_source_root_is_safe():
    assert free_noop_template(_alg("free_buffer", "()", _buf()), None) is None
