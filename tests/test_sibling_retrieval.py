"""Regression: intra-subject sibling retrieval injects a verified same-shape
sibling as a worked exemplar, and only when the signature shape matches."""
from types import SimpleNamespace

from alchemist.implementer.tdd_generator import TDDGenerator


def _alg(name, inputs, ret):
    ins = [SimpleNamespace(name=n, rust_type=t) for n, t in inputs]
    return SimpleNamespace(name=name, inputs=ins, return_type=ret)


def _gen():
    # Construct without hitting a real LLM: pass a dummy llm object.
    return TDDGenerator(llm=SimpleNamespace(stats={}))


def test_shape_key_is_name_independent():
    g = _gen()
    a = _alg("tinyjambu128_p1024", [("r#in", "&[u8]")], "Vec<u8>")
    b = _alg("tinyjambu256_p1024", [("r#in", "&[u8]")], "Vec<u8>")
    assert g._sig_shape_key(a) == g._sig_shape_key(b)


def test_exemplar_fires_only_on_shape_match():
    g = _gen()
    # a verified sibling with the buf_transform shape
    g._verified_siblings.append({
        "name": "tinyjambu128_p1024",
        "shape_key": g._sig_shape_key(_alg("tinyjambu128_p1024", [("r#in", "&[u8]")], "Vec<u8>")),
        "sig": "pub fn tinyjambu128_p1024(r#in: &[u8]) -> Vec<u8>",
        "body": "\n    let mut buf = [0u8; 32];\n    buf.to_vec()\n",
    })
    # same shape, different name -> exemplar fires
    same = _alg("tinyjambu256_p1024", [("r#in", "&[u8]")], "Vec<u8>")
    block = g._sibling_exemplar_block(same)
    assert "Verified sibling" in block and "tinyjambu128_p1024" in block

    # different shape -> no exemplar
    other = _alg("fix16_mul", [("a", "i32"), ("b", "i32")], "i32")
    assert g._sibling_exemplar_block(other) == ""

    # same function name as the only sibling -> no self-exemplar
    itself = _alg("tinyjambu128_p1024", [("r#in", "&[u8]")], "Vec<u8>")
    assert g._sibling_exemplar_block(itself) == ""
