"""c2rust-baseline route — oracle-gated safe-ification of unsafe-correct Rust.

The end-to-end (unsafe raw-pointer baseline -> safe, byte-exact via cargo test) is
proven on the box; here we lock the already-safe short-circuit and the front-end probe.
"""

from alchemist.autonomy.safeify import safeify, c2rust_available


def test_c2rust_available_returns_bool():
    assert isinstance(c2rust_available(), bool)   # pluggable front-end probe


def test_safeify_short_circuits_already_safe(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text("pub fn f(s: &[u8]) -> u32 { s.iter().map(|&b| b as u32).sum() }\n")
    # no unsafe / raw pointers -> no model call needed
    assert safeify(f, lambda: True, llm=None) == "already-safe"


def test_safeify_preserves_correct_floor_when_model_absent(tmp_path):
    f = tmp_path / "lib.rs"
    unsafe = ("pub fn f(d: &[u8]) -> u32 { let p = d.as_ptr(); "
              "unsafe { *p as u32 } }\n")
    f.write_text(unsafe)
    # llm=None -> candidate is None -> revert to the correct unsafe floor (partial)
    assert safeify(f, lambda: True, llm=None) == "partial"
    assert f.read_text() == unsafe                # correctness never lost
