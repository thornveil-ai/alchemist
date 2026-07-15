"""Tests for the post-architect trait extractor."""

from __future__ import annotations

from alchemist.architect.schemas import (
    CrateArchitecture,
    CrateSpec,
    TraitSpec,
)
from alchemist.architect.trait_extractor import (
    _Shape,
    _shape_for,
    extract_traits,
)
from alchemist.extractor.schemas import (
    AlgorithmSpec,
    ModuleSpec,
    Parameter,
)


def _checksum(name: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name, display_name=name, category="checksum",
        description="",
        inputs=[Parameter(name="input", rust_type="&[u8]", description="")],
        return_type="u32",
    )


def _hash(name: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name, display_name=name, category="hash",
        description="",
        inputs=[Parameter(name="input", rust_type="&[u8]", description="")],
        return_type="Vec<u8>",
    )


def _arch_with_crate(crate_name: str, module_names: list[str]) -> CrateArchitecture:
    return CrateArchitecture(
        workspace_name="test",
        description="",
        crates=[CrateSpec(
            name=crate_name, description="", modules=module_names,
        )],
    )


def test_shape_for_returns_none_on_no_inputs():
    alg = AlgorithmSpec(
        name="f", display_name="", category="checksum",
        description="", inputs=[], return_type="u32",
    )
    assert _shape_for(alg) is None


def test_shape_groups_identical_signatures():
    a = _checksum("adler32")
    b = _checksum("crc32")
    assert _shape_for(a) == _shape_for(b)


def test_shape_distinguishes_categories():
    a = _checksum("adler32")
    h = _hash("sha256")
    # Return type differs → different shape
    assert _shape_for(a) != _shape_for(h)


def test_shape_distinguishes_return_types():
    a = AlgorithmSpec(
        name="a", display_name="", category="checksum",
        description="",
        inputs=[Parameter(name="i", rust_type="&[u8]", description="")],
        return_type="u32",
    )
    b = AlgorithmSpec(
        name="b", display_name="", category="checksum",
        description="",
        inputs=[Parameter(name="i", rust_type="&[u8]", description="")],
        return_type="u64",
    )
    assert _shape_for(a) != _shape_for(b)


def test_extract_emits_checksum_trait():
    mod = ModuleSpec(
        name="checksums", display_name="", description="",
        algorithms=[_checksum("adler32"), _checksum("crc32")],
    )
    arch = _arch_with_crate("zlib-checksum", ["checksums"])
    traits = extract_traits([mod], arch)
    assert len(traits) == 1
    t = traits[0]
    assert t.name == "Checksum"
    assert t.crate == "zlib-checksum"
    assert set(t.implementors) == {"adler32", "crc32"}


def test_extract_skips_solo_family():
    mod = ModuleSpec(
        name="m", display_name="", description="",
        algorithms=[_checksum("adler32")],  # only one
    )
    arch = _arch_with_crate("zlib-checksum", ["m"])
    traits = extract_traits([mod], arch, min_implementors=2)
    assert traits == []


def test_extract_skips_existing_traits():
    mod = ModuleSpec(
        name="m", display_name="", description="",
        algorithms=[_checksum("adler32"), _checksum("crc32")],
    )
    arch = CrateArchitecture(
        workspace_name="t", description="",
        crates=[CrateSpec(name="zlib-checksum", description="", modules=["m"])],
        traits=[TraitSpec(
            name="Checksum",
            description="already declared",
            methods=[],
            crate="zlib-checksum",
        )],
    )
    traits = extract_traits([mod], arch)
    assert traits == []


def test_extract_uses_hasher_name_for_hash_category():
    mod = ModuleSpec(
        name="m", display_name="", description="",
        algorithms=[_hash("sha256"), _hash("md5")],
    )
    arch = _arch_with_crate("zlib-hash", ["m"])
    traits = extract_traits([mod], arch)
    assert len(traits) == 1
    assert traits[0].name == "Hasher"


def test_extract_groups_across_modules():
    m1 = ModuleSpec(
        name="adler", display_name="", description="",
        algorithms=[_checksum("adler32")],
    )
    m2 = ModuleSpec(
        name="crc", display_name="", description="",
        algorithms=[_checksum("crc32")],
    )
    arch = _arch_with_crate("zlib-checksum", ["adler", "crc"])
    traits = extract_traits([m1, m2], arch)
    assert len(traits) == 1
    assert set(traits[0].implementors) == {"adler32", "crc32"}


def _str_lookup(name: str) -> AlgorithmSpec:
    # http-parser's http_errno_name/http_method_str etc: enum -> &'static str
    return AlgorithmSpec(
        name=name, display_name=name, category="utility",
        description="",
        inputs=[Parameter(name="e", rust_type="HttpErrno", description="")],
        return_type="&'static str",
    )


def _hash_update(name: str) -> AlgorithmSpec:
    return AlgorithmSpec(
        name=name, display_name=name, category="hash",
        description="",
        inputs=[Parameter(name="s", rust_type="&mut HashState", description=""),
                Parameter(name="d", rust_type="&[u8]", description="")],
        return_type="()",
    )


def test_static_str_return_renders_with_space():
    # REGRESSION: _normalize_type collapsed `&'static str` -> `&'staticstr` and that
    # whitespace-collapsed string was rendered into the trait signature -> the crate
    # would not compile. This broke every str_lookup library (http-parser). The trait
    # signature must render from the member's ORIGINAL, properly-spaced type.
    mod = ModuleSpec(name="m", display_name="m", description="",
                     algorithms=[_str_lookup("http_errno_name"),
                                 _str_lookup("http_method_str")])
    traits = extract_traits([mod], _arch_with_crate("core", ["m"]))
    assert traits, "expected a Utility trait for the 2 str_lookup members"
    sig = traits[0].methods[0].signature
    assert "&'static str" in sig, f"space dropped: {sig!r}"
    assert "'staticstr" not in sig, f"invalid Rust emitted: {sig!r}"


def test_mut_self_promotion_renders_with_spaced_type():
    # The &self/&mut self promotion matched on `"&mut "`; against the space-collapsed
    # `&mutHashState` it never matched. Rendering from the original type fixes both.
    mod = ModuleSpec(name="m", display_name="m", description="",
                     algorithms=[_hash_update("a"), _hash_update("b")])
    traits = extract_traits([mod], _arch_with_crate("core", ["m"]))
    assert traits, "expected a Hasher trait"
    sig = traits[0].methods[0].signature
    assert "&mut self" in sig, f"&mut self promotion broken: {sig!r}"


def test_emit_trait_adds_sized_bound_for_self_returning_method():
    # Model-designed trait returning Self by value (http-parser: fn parse(..) ->
    # Result<Self, ParseError>) must get `where Self: Sized` or it fails E0277 and
    # aborts the whole run. Deterministic emitter repair; borrowed Self is untouched.
    from alchemist.implementer.skeleton import emit_trait
    from alchemist.architect.schemas import TraitSpec, TraitMethod
    t = TraitSpec(
        name="Protocol", description="", crate="core",
        methods=[
            TraitMethod(name="parse", description="",
                        signature="fn parse(buf: &[u8]) -> Result<Self, ParseError>"),
            TraitMethod(name="peek", description="", signature="fn peek(&self) -> &Self"),
        ],
    )
    out = emit_trait(t)
    assert "fn parse(buf: &[u8]) -> Result<Self, ParseError> where Self: Sized;" in out
    assert "fn peek(&self) -> &Self;" in out  # borrowed Self: no bound added
