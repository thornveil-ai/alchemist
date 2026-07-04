"""Catalog name-matching must respect variant boundaries (no false oracles)."""

from __future__ import annotations

from alchemist.standards.catalog import lookup_test_vectors, match_algorithm


def test_crc16_does_not_match_crc32_catalog():
    """crc16_ccitt is a distinct 16-bit algorithm — it must NOT be handed
    CRC-32's 32-bit vectors, which would fail a correct implementation."""
    assert match_algorithm("crc16_ccitt") is None
    assert lookup_test_vectors("crc16_ccitt") == []


def test_legitimate_prefix_matches_preserved():
    assert match_algorithm("crc32") == "crc32"
    assert match_algorithm("crc32_z") == "crc32"
    assert match_algorithm("crc32_ieee") == "crc32"
    assert match_algorithm("adler32_impl") == "adler32"
    assert match_algorithm("crc") == "crc32"  # bare "crc" alias still resolves


def test_unknown_names_return_none():
    assert match_algorithm("fnv1a32") is None
    assert match_algorithm("bsd_sum16") is None
    assert match_algorithm("crc16") is None
