"""str_lookup oracle: `const char* f(<scalar/enum>)` — enum/int -> static NUL-terminated
string. The universal C `<enum>_name()` / `_to_string()` idiom (http-parser's
http_method_str / http_status_str / http_errno_name / http_errno_description). No prior
oracle covered a SCALAR-in string-out lookup, so http-parser's verified core was nearly
all-refused. Fuzz the scalar, compare the returned string byte-exact; NULL returns
(unknown-enum boundary) are skipped.
"""
from __future__ import annotations

import ctypes
import shutil
import tempfile
from pathlib import Path

import pytest

from alchemist.verifier.auto_config import classify_str_lookup, fuzz_str_lookup_vectors
from alchemist.extractor.schemas import AlgorithmSpec


class _Sig:
    def __init__(self, name, ret, params):
        self.name, self.return_type, self.params = name, ret, params


def test_classify_scalar_and_enum_params():
    assert classify_str_lookup(_Sig("f", "const char *", [("m", "int")])) == "str_lookup"
    assert classify_str_lookup(_Sig("g", "char *", [("e", "enum http_method")])) == "str_lookup"
    assert classify_str_lookup(_Sig("h", "const char *", [("e", "unsigned")])) == "str_lookup"


def test_reject_non_lookups():
    assert classify_str_lookup(_Sig("a", "int", [("m", "int")])) is None            # scalar ret
    assert classify_str_lookup(_Sig("b", "char *", [("s", "const char *")])) is None  # cstr_out
    assert classify_str_lookup(_Sig("c", "char *", [("a", "int"), ("b", "int")])) is None  # 2 args


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc required")
def test_byte_exact_enum_to_string(tmp_path):
    from alchemist.verifier.auto_ffi import build_c_dll
    from alchemist.verifier.build_c_dll import discover_c_build
    from alchemist.verifier.auto_config import collect_subject_signatures
    d = tmp_path
    (d / "c.c").write_text(
        'const char *color_name(int c){switch(c){'
        'case 0:return "red";case 1:return "green";case 2:return "blue";default:return 0;}}')
    sig = {s.name: s for s in collect_subject_signatures(d)}["color_name"]
    assert classify_str_lookup(sig) == "str_lookup"
    cf, inc = discover_c_build(d)
    dll_path = d / "c.dll"
    build = build_c_dll(cf, dll_path, include_dirs=inc)
    if not build.success:
        pytest.skip(f"DLL build failed: {build}")
    dll = ctypes.CDLL(str(dll_path))
    alg = AlgorithmSpec(name="color_name", display_name="x", category="utility",
                        description="", inputs=[], return_type="&'static str")
    bodies = [v.expected_output for v in fuzz_str_lookup_vectors(dll, alg, sig)]
    assert any('color_name(0), "red"' in b for b in bodies)
    assert any('color_name(1), "green"' in b for b in bodies)
    assert any('color_name(2), "blue"' in b for b in bodies)
    assert not any("color_name(3)" in b for b in bodies)   # NULL default skipped


def test_return_flavor_string_and_option():
    """Owned String -> `.as_str()`; Option<&str> -> `Some(...)`."""
    sig = _Sig("f", "const char *", [("m", "int")])

    class _DummyDll:
        class _F:
            restype = None
            argtypes = None
            def __call__(self, v):
                return b"X" if v == 0 else None
        def __getattr__(self, n):
            return self._F()

    dll = _DummyDll()
    body_string = fuzz_str_lookup_vectors(
        dll, AlgorithmSpec(name="f", display_name="f", category="utility", description="",
                           inputs=[], return_type="String"), sig, count=2)[0].expected_output
    assert ".as_str(), \"X\"" in body_string
    body_opt = fuzz_str_lookup_vectors(
        dll, AlgorithmSpec(name="f", display_name="f", category="utility", description="",
                           inputs=[], return_type="Option<&str>"), sig, count=2)[0].expected_output
    assert 'Some("X")' in body_opt
