"""ALCHEMIST_SAFE_SCALAR clamps int scalar fuzzing to the char domain [-1,255]
so contract-domain / glibc-ctype functions (luaO_hexavalue) get valid oracle
inputs instead of segfaulting, and the proptest differential fuzzes the SAME
bounded domain."""
import ctypes, os, shutil
import pytest
from types import SimpleNamespace
from alchemist.verifier.auto_ffi import parse_header, build_c_dll

_HAS_GCC = shutil.which("gcc") is not None
gcc_only = pytest.mark.skipif(not _HAS_GCC, reason="gcc not on PATH")


@gcc_only
def test_safe_scalar_clamps_fuzz_domain(tmp_path, monkeypatch):
    src = tmp_path / "h.c"
    src.write_text("#include <ctype.h>\n"
                   "int hexv(int c){ if(isdigit(c)) return c-'0'; return (tolower(c)-'a')+10; }\n")
    dll = tmp_path / ("h.dll" if os.name == "nt" else "h.so")
    assert build_c_dll([src], dll).success
    from alchemist.verifier.auto_config import fuzz_scalar_vectors
    sig = parse_header("int hexv(int c);")[0]
    alg = SimpleNamespace(name="hexv", inputs=[SimpleNamespace(name="c", rust_type="i32")])
    monkeypatch.setenv("ALCHEMIST_SAFE_SCALAR", "1")
    vecs = fuzz_scalar_vectors(ctypes.CDLL(str(dll)), alg, sig, count=40)
    assert vecs
    for v in vecs:
        val = int(v.inputs["c"].replace("i32", ""))
        assert -1 <= val <= 255, f"value {val} outside safe domain"


def test_proptest_strategy_bounded_under_safe_scalar(monkeypatch, tmp_path):
    # build_diff_config emits a bounded strategy for a scalar fn when flagged.
    if not _HAS_GCC:
        pytest.skip("gcc")
    src = tmp_path / "h.c"; src.write_text("int f(int c){return c;}\n")
    (tmp_path / "h.h").write_text("int f(int c);\n")
    from alchemist.verifier.auto_config import build_diff_config
    specs = [SimpleNamespace(name="h", algorithms=[SimpleNamespace(
        name="f", category="utility",
        inputs=[SimpleNamespace(name="c", rust_type="i32")], outputs=[], invariants=[],
        return_type="i32")])]
    monkeypatch.setenv("ALCHEMIST_SAFE_SCALAR", "1")
    cfg = build_diff_config(tmp_path, specs)
    if cfg is None:
        pytest.skip("no config (env-specific)")
    h = [x for x in cfg.harnesses if x.algorithm == "f"]
    assert h and "..=255i32" in h[0].input_strategy
    assert "any::<" not in h[0].input_strategy
