"""The consolidated mechanical-repair loop (borrow + type + method, no model)."""

import tempfile
from pathlib import Path

from alchemist.autonomy.mechanical import mechanical_repair


def _mod(text):
    f = Path(tempfile.mkdtemp()) / "lib.rs"
    f.write_text(text)
    return f


def test_repairs_type_then_reports_clean():
    f = _mod("fn f() {\n    c ^= s[k];\n}")
    # stateful build: reports the error until the cast is applied
    def build():
        return "" if "as u8" in f.read_text() else \
            "error[E0277]: no implementation for `u8 ^= u32`\n   --> src/lib.rs:2:5"
    assert mechanical_repair(f, build) is True
    assert "as u8" in f.read_text()


def test_repairs_method_hallucination():
    f = _mod("fn f(a: u64) -> u64 { a.wrapping_rotate_left(13) }")
    def build():
        return "" if "wrapping_rotate_left" not in f.read_text() else \
            "error[E0599]: no method named `wrapping_rotate_left` found"
    assert mechanical_repair(f, build) is True
    assert "rotate_left(13)" in f.read_text()


def test_clean_build_is_true_immediately():
    f = _mod("fn f() {}")
    assert mechanical_repair(f, lambda: "") is True


def test_unfixable_returns_false():
    f = _mod("fn f() {}")
    # a persistent error none of the fixers handle -> False (hand to the diagnoser)
    assert mechanical_repair(f, lambda: "error[E0412]: cannot find type `Widget`", rounds=2) is False
