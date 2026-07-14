"""The all-scalar shape must treat a C `enum` as int-sized (and strip `const`), so an
enum state-machine step like `enum state parse_url_char(enum state, const char)` — the
core of http-parser's goto parser — classifies + fuzzes as scalars. Plain scalar
functions must be unaffected."""
from alchemist.verifier.auto_config import classify_scalar_shape, _norm_scalar


class _Sig:
    def __init__(self, name, ret, params):
        self.name, self.return_type, self.params = name, ret, params


def test_norm_scalar():
    assert _norm_scalar("enum state") == "int"
    assert _norm_scalar("const char") == "char"
    assert _norm_scalar("uint32_t") == "uint32_t"


def test_enum_state_machine_step_classifies():
    assert classify_scalar_shape(
        _Sig("step", "enum state", [("s", "enum state"), ("c", "const char")])) == "scalar"


def test_plain_scalars_unaffected():
    assert classify_scalar_shape(_Sig("isqrt", "unsigned", [("x", "unsigned")])) == "scalar"
    assert classify_scalar_shape(
        _Sig("crc", "uint32_t", [("s", "uint32_t"), ("b", "unsigned char")])) == "scalar"


def test_non_scalar_rejected():
    assert classify_scalar_shape(_Sig("f", "char *", [("x", "int")])) is None   # ptr ret
    assert classify_scalar_shape(_Sig("g", "int", [("p", "int *")])) is None      # ptr arg
