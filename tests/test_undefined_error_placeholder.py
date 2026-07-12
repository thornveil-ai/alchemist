"""P1: the architect sometimes emits a trait method returning `Result<_, SomeError>`
without defining SomeError (base64's Decoder::decode -> Result<Vec<u8>, DecodeError>).
An undefined type breaks the WHOLE crate's compile, so the library fills 0 functions.
The skeleton now emits a minimal placeholder for any error type a trait references
but that isn't defined or imported — so the skeleton compiles and the fill loop runs."""

from __future__ import annotations

from alchemist.implementer.skeleton import _lib_rs_for
from alchemist.architect.schemas import CrateSpec, TraitSpec, TraitMethod


def _crate():
    return CrateSpec(name="base64-traits", description="t", modules=[], dependencies=[])


def _trait(sig):
    return TraitSpec(name="Decoder", description="d", crate="base64-traits",
                     methods=[TraitMethod(name="decode", signature=sig, description="d")])


def test_undefined_error_gets_placeholder():
    # nested generic in the Ok arm must not trip the extraction
    out = _lib_rs_for(_crate(), [], [], [_trait(
        "fn decode(&self, input: &str) -> Result<Vec<u8>, DecodeError>")],
        no_std=False, dep_crate_names=[])
    assert "pub struct DecodeError;" in out
    assert "impl core::fmt::Display for DecodeError" in out


def test_defined_error_not_duplicated():
    from alchemist.architect.schemas import ErrorType, ErrorVariant
    err = ErrorType(name="DecodeError", crate="base64-traits",
                    variants=[ErrorVariant(name="Invalid", description="x", fields=[])])
    out = _lib_rs_for(_crate(), [], [err], [_trait(
        "fn decode(&self, input: &str) -> Result<Vec<u8>, DecodeError>")],
        no_std=False, dep_crate_names=[])
    # the real enum is emitted; the placeholder struct is NOT (would be a dup)
    assert "pub enum DecodeError" in out
    assert "pub struct DecodeError;" not in out


def test_std_containers_not_placeheld():
    out = _lib_rs_for(_crate(), [], [], [_trait(
        "fn f(&self) -> Result<Vec<u8>, Self>")], no_std=False, dep_crate_names=[])
    assert "pub struct Self;" not in out
