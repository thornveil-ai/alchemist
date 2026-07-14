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


def test_module_signature_referenced_type_gets_placeholder():
    # parson: json_serialize_to_buffer(..) -> Result<(), SerializationError> where
    # SerializationError is invented by the extractor and never defined. With NO
    # dependency crates, the broad module-signature scan must placehold it so the
    # module compiles and the fn honestly refuses (fail-closed).
    out = _lib_rs_for(_crate(), [], [], [], no_std=True, dep_crate_names=[],
                      sig_referenced_types={"SerializationError", "ValidationError",
                                            "JsonValue", "Box", "Vec"})
    assert "pub struct SerializationError;" in out
    assert "pub struct ValidationError;" in out
    # std/alloc containers and (undefined-here-but-carried) domain structs behave:
    # Box/Vec are known and never placeheld; JsonValue (a real carried struct in the
    # module, re-exported via `pub use self::*`) is not an error type — but with no
    # crate_defined_types passed it WOULD placehold. Assert the container guard only.
    assert "pub struct Box;" not in out
    assert "pub struct Vec;" not in out


def test_defined_module_type_not_placeheld():
    # A domain struct the crate's own module defines must NOT be placeheld even if a
    # signature references it (would duplicate-define).
    out = _lib_rs_for(_crate(), [], [], [], no_std=True, dep_crate_names=[],
                      crate_defined_types={"JsonValue"},
                      sig_referenced_types={"JsonValue", "SerializationError"})
    assert "pub struct JsonValue;" not in out
    assert "pub struct SerializationError;" in out


def test_dep_crate_disables_broad_signature_scan():
    # With a dependency crate present, a sig-referenced type may come from that
    # crate's glob re-export; the broad scan is disabled to avoid duplicate defs.
    out = _lib_rs_for(_crate(), [], [], [], no_std=True, dep_crate_names=["zlib-types"],
                      sig_referenced_types={"DeflateState"})
    assert "pub struct DeflateState;" not in out


def test_no_std_module_imports_alloc_box():
    # no_std module must bring bare Box/Vec/String into scope so a signature like
    # `-> Option<Box<JsonValue>>` (parson) resolves (E0425 otherwise).
    from alchemist.implementer.skeleton import _module_rs_for
    from alchemist.extractor.schemas import ModuleSpec
    m = ModuleSpec(name="parson", display_name="parson", description="d",
                   algorithms=[], shared_types=[])
    out_no_std = _module_rs_for(m, {}, dep_crate_names=[], no_std=True)
    assert "use alloc::boxed::Box;" in out_no_std
    out_std = _module_rs_for(m, {}, dep_crate_names=[], no_std=False)
    assert "use alloc::boxed::Box;" not in out_std
