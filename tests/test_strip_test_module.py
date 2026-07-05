"""Fill prompt must strip the test module or it overflows model context."""
from alchemist.implementer.tdd_generator import TDDGenerator


def test_strips_test_module_keeps_code():
    src = ("use foo::*;\npub fn a() { 1 }\npub const X: u32 = 5;\n"
           "#[cfg(test)]\nmod tests {\n    #[test]\n    fn t() { if true { let _=1; } }\n}\n")
    out = TDDGenerator._strip_test_module(src)
    assert "pub fn a()" in out and "pub const X" in out
    assert "#[cfg(test)]" not in out and "fn t()" not in out


def test_no_test_module_is_noop():
    src = "pub fn a() {}\n"
    assert TDDGenerator._strip_test_module(src) == src


def test_preserves_code_after_test_module():
    src = "pub fn a(){}\n#[cfg(test)]\nmod tests { fn t(){} }\npub fn b(){}\n"
    out = TDDGenerator._strip_test_module(src)
    assert "pub fn a()" in out and "pub fn b()" in out and "fn t()" not in out
