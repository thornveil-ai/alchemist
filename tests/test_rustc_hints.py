"""Error-code-specific rustc repair hints: turn a recurring compile error into
the structural fix so the model stops looping on it (e.g. sha256_update E0502)."""
from alchemist.implementer.tdd_generator import _rustc_error_hints


def test_borrow_conflict_hint():
    h = _rustc_error_hints("error[E0502]: cannot borrow `*ctx` as mutable")
    assert "E0502" in h and "copy the values you read into local" in h


def test_type_mismatch_hint():
    h = _rustc_error_hints("error[E0308]: mismatched types\nexpected u32, found u8")
    assert "E0308" in h and "as" in h


def test_multiple_codes_deduped_and_capped():
    cerr = ("error[E0502]: x\nerror[E0502]: y\nerror[E0308]: z\n"
            "error[E0382]: a\nerror[E0384]: b\nerror[E0277]: c")
    h = _rustc_error_hints(cerr)
    # E0502 appears once despite two occurrences; capped at 4 codes
    assert h.count("E0502 (borrow conflict)") == 1
    assert h.count("- E") <= 4


def test_unknown_code_silent():
    assert _rustc_error_hints("error[E9999]: made up") == ""
    assert _rustc_error_hints("no error codes at all") == ""
