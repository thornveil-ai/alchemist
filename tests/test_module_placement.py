"""Architecture reconciliation: every spec module lands in exactly one crate.

Regression for the hashkit failure: the architect listed function names in
crate.modules instead of the real module name, so the skeleton emitted empty
crates (0 functions) and the differential adapter found nothing to bind.
"""

from __future__ import annotations

from alchemist.pipeline import _reconcile_module_placement
from alchemist.architect.schemas import CrateArchitecture, CrateSpec
from alchemist.extractor.schemas import (
    AlgorithmSpec, ModuleSpec, Parameter,
)


def _alg(n):
    return AlgorithmSpec(
        name=n, display_name=n, category="checksum", description="",
        inputs=[Parameter(name="buf", rust_type="&[u8]", description="")],
        return_type="u32")


def _cs(name, mods, deps=None):
    return CrateSpec(name=name, description="c", modules=mods,
                     dependencies=deps or [])


def _arch(crates):
    return CrateArchitecture(workspace_name="ws", description="d", crates=crates)


def test_function_names_as_modules_collapse_to_single_owner():
    specs = [ModuleSpec(name="hashkit", display_name="", description="",
                        algorithms=[_alg("fnv1a32"), _alg("crc16_ccitt"),
                                    _alg("bsd_sum16")])]
    arch = _arch([
        _cs("hashkit-core", []),
        _cs("hashkit-hash", ["fnv1a32"]),
        _cs("hashkit-checksum", ["crc16_ccitt", "bsd_sum16"]),
    ])
    _reconcile_module_placement(arch, specs)
    owners = [c.name for c in arch.crates if "hashkit" in (c.modules or [])]
    assert len(owners) == 1, owners
    # Every remaining crate references only REAL module names
    for c in arch.crates:
        for m in c.modules or []:
            assert m in {"hashkit"}


def test_unclaimed_module_gets_placed_somewhere():
    specs = [ModuleSpec(name="tinychk", display_name="", description="",
                        algorithms=[_alg("adler32")])]
    arch = _arch([_cs("tinychk-checksums", [])])  # module claimed by nobody
    _reconcile_module_placement(arch, specs)
    assert any("tinychk" in (c.modules or []) for c in arch.crates)


def test_correct_placement_is_preserved():
    specs = [ModuleSpec(name="tinychk", display_name="", description="",
                        algorithms=[_alg("adler32")])]
    arch = _arch([
        _cs("tinychk-checksums", ["tinychk"]),
        _cs("tinychk-core", []),
    ])
    _reconcile_module_placement(arch, specs)
    owners = [c.name for c in arch.crates if "tinychk" in (c.modules or [])]
    assert owners == ["tinychk-checksums"]


def test_type_only_crate_is_kept_even_without_modules():
    from alchemist.architect.schemas import ErrorType, ErrorVariant
    specs = [ModuleSpec(name="lib", display_name="", description="",
                        algorithms=[_alg("f")])]
    arch = _arch([
        _cs("lib-impl", ["lib"], deps=["lib-types"]),
        _cs("lib-types", []),
    ])
    arch.error_types = [ErrorType(
        name="LibError", crate="lib-types",
        variants=[ErrorVariant(name="Bad", description="", fields=[])])]
    _reconcile_module_placement(arch, specs)
    names = {c.name for c in arch.crates}
    assert "lib-types" in names  # kept: holds an error type + is depended on
    assert "lib-impl" in names


# ---------- error-type + builder reconciliation ----------

def test_unknown_error_type_remapped_to_crate_canonical():
    from alchemist.pipeline import _reconcile_error_types
    from alchemist.architect.schemas import ErrorType, ErrorVariant
    specs = [ModuleSpec(name="siphash", display_name="", description="",
                        algorithms=[AlgorithmSpec(
                            name="siphash", display_name="siphash",
                            category="hash", description="",
                            inputs=[Parameter(name="in_", rust_type="&[u8]", description="")],
                            return_type="Result<Vec<u8>, HashError>")])]
    arch = _arch([_cs("siphash-core", ["siphash"])])
    arch.error_types = [ErrorType(name="SipHashError", crate="siphash-core",
                                  variants=[ErrorVariant(name="Bad", description="", fields=[])])]
    n = _reconcile_error_types(arch, specs)
    assert n == 1
    assert specs[0].algorithms[0].return_type == "Result<Vec<u8>, SipHashError>"


def test_known_error_type_left_alone():
    from alchemist.pipeline import _reconcile_error_types
    from alchemist.architect.schemas import ErrorType, ErrorVariant
    specs = [ModuleSpec(name="m", display_name="", description="",
                        algorithms=[AlgorithmSpec(
                            name="f", display_name="f", category="hash", description="",
                            inputs=[Parameter(name="x", rust_type="&[u8]", description="")],
                            return_type="Result<Vec<u8>, MyError>")])]
    arch = _arch([_cs("c", ["m"])])
    arch.error_types = [ErrorType(name="MyError", crate="c",
                                  variants=[ErrorVariant(name="B", description="", fields=[])])]
    assert _reconcile_error_types(arch, specs) == 0
    assert specs[0].algorithms[0].return_type == "Result<Vec<u8>, MyError>"


def test_dangling_builder_dropped():
    from alchemist.pipeline import _prune_dangling_builders
    from alchemist.architect.schemas import BuilderSpec
    arch = _arch([_cs("c", ["m"])])
    arch.builders = [BuilderSpec(builder_name="SipHasherBuilder",
                                 built_type="SipHasher", crate="c",
                                 parameters=[], build_signature="x")]
    assert _prune_dangling_builders(arch) == 1
    assert arch.builders == []
