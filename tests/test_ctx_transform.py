"""ctx_transform decomposition shape: the offline equivalence gate must accept
a behaviour-preserving split of a struct-state block transform and reject a
buggy one. Uses the real sha256_transform. Skips if gcc is unavailable."""
import shutil
from pathlib import Path

import pytest

from alchemist.implementer.structural_decomp import (
    Decomposition,
    classify_ctx_transform_proto,
    verify_c_decomposition_equivalent,
)

_SHA = Path(__file__).resolve().parent.parent / "subjects" / "sha256" / "sha256.c"
pytestmark = pytest.mark.skipif(
    shutil.which("gcc") is None or not _SHA.exists(),
    reason="needs gcc + subjects/sha256",
)


def _slice_transform():
    src = _SHA.read_text()
    i = src.index("void sha256_transform")
    depth = 0
    started = False
    end = i
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
            started = True
        elif src[j] == "}":
            depth -= 1
            if started and depth == 0:
                end = j + 1
                break
    return src[:i], src[i:end]


def test_classifier():
    assert classify_ctx_transform_proto(
        "void sha256_transform(SHA256_CTX *ctx, const BYTE data[])"
    ) == ("sha256_transform", "SHA256_CTX")
    # a plain buffer codec is NOT a ctx_transform
    assert classify_ctx_transform_proto(
        "int base64_encode(const BYTE in[], BYTE out[], size_t n)"
    ) is None


def test_identity_split_verifies_byte_exact():
    preamble, transform = _slice_transform()
    inc = [(_SHA.parent).resolve()]
    d = Decomposition(original_name="sha256_transform", helpers=[],
                      driver_source=transform)
    ok, rep = verify_c_decomposition_equivalent(
        original_c=transform, decomposition=d, fn_name="sha256_transform",
        shape="ctx_transform", include_dirs=inc, preamble=preamble, n=32)
    assert ok is True, rep


def test_buggy_split_is_caught():
    preamble, transform = _slice_transform()
    inc = [(_SHA.parent).resolve()]
    buggy = transform.replace("ctx->state[0] += a;", "ctx->state[0] += b;")
    assert buggy != transform
    d = Decomposition(original_name="sha256_transform", helpers=[],
                      driver_source=buggy)
    ok, rep = verify_c_decomposition_equivalent(
        original_c=transform, decomposition=d, fn_name="sha256_transform",
        shape="ctx_transform", include_dirs=inc, preamble=preamble, n=32)
    assert ok is False and "DIVERGENCE" in rep
