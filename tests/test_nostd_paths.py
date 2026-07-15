"""no_std path fix: the model's `std::` in a no_std crate (E0433, siphash's 0)
is mechanically rewritten to core::/alloc:: before compiling."""
from alchemist.implementer.tdd_generator import _rewrite_std_for_no_std, _rustc_error_hints


def test_core_paths():
    assert _rewrite_std_for_no_std("std::mem::swap(a, b)") == "core::mem::swap(a, b)"
    assert _rewrite_std_for_no_std("std::convert::TryInto") == "core::convert::TryInto"
    assert _rewrite_std_for_no_std("std::cmp::min(a, b)") == "core::cmp::min(a, b)"


def test_alloc_paths():
    assert _rewrite_std_for_no_std("std::vec::Vec::new()") == "alloc::vec::Vec::new()"
    assert _rewrite_std_for_no_std("std::string::String") == "alloc::string::String"
    assert _rewrite_std_for_no_std("std::boxed::Box") == "alloc::boxed::Box"


def test_macros():
    assert _rewrite_std_for_no_std('std::format!("x")') == 'alloc::format!("x")'
    assert _rewrite_std_for_no_std("std::vec![1, 2]") == "alloc::vec![1, 2]"


def test_leaves_core_and_alloc_alone():
    src = "core::mem::swap(a, b); alloc::vec::Vec::new()"
    assert _rewrite_std_for_no_std(src) == src


def test_e0433_hint():
    assert "no_std" in _rustc_error_hints("error[E0433]: cannot find crate `std`")
