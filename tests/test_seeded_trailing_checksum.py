"""Seed-as-trailing-arg checksum shape: `hash(const char* data, size_t len,
unsigned seed)` (Lua luaS_hash, FNV/murmur variants). Previously unrecognized
-> no fuzz vectors -> function unverifiable. This was the first framework gap the
Lua beachhead exposed (luaS_hash: 'no test vectors — skipping').
"""

from __future__ import annotations

from types import SimpleNamespace

from alchemist.verifier.auto_ffi import parse_header
from alchemist.verifier.auto_config import classify_checksum_shape, _binding_for
from alchemist.verifier.adapter_gen import _resolve_checksum_rust, _resolve_checksum_c


def test_classify_seeded_trailing():
    sig = parse_header("unsigned int luaS_hash(const char *str, size_t l, unsigned int seed);")[0]
    assert classify_checksum_shape(sig) == "seeded_trailing"


def test_classify_seeded_first_still_works():
    sig = parse_header("unsigned long adler32(unsigned long a, const unsigned char *buf, unsigned int len);")[0]
    assert classify_checksum_shape(sig) == "seeded"


def test_binding_trailing_seed_arg_order():
    sig = parse_header("unsigned int luaS_hash(const char *str, size_t l, unsigned int seed);")[0]
    b = _binding_for(sig, "seeded_trailing", 5)
    # (ptr, len, seed) — three argtypes, seed last
    assert len(b.argtypes) == 3


def _fn(name, params, ret):
    return SimpleNamespace(name=name, params=params, ret=ret,
                           crate_ident="lua_hash_core")


def test_adapter_rust_seed_trailing_len_folded():
    # Model produced fn(str: &[u8], seed: u32) -> u32 (len folded into slice)
    h = SimpleNamespace(algorithm="lua_s_hash", category="hash", seed=5, seed_trailing=True)
    api = {"lua_s_hash": [_fn("lua_s_hash", [("str", "&[u8]"), ("seed", "u32")], "u32")]}
    body, ret, _ = _resolve_checksum_rust(h, api)
    assert body == "lua_hash_core::lua_s_hash(data, 5u32)"
    assert ret == "u32"


def test_adapter_rust_seed_trailing_len_kept():
    h = SimpleNamespace(algorithm="lua_s_hash", category="hash", seed=5, seed_trailing=True)
    api = {"lua_s_hash": [_fn("lua_s_hash", [("s", "&[u8]"), ("l", "usize"), ("seed", "u32")], "u32")]}
    body, _, _ = _resolve_checksum_rust(h, api)
    assert body == "lua_hash_core::lua_s_hash(data, data.len(), 5u32)"


def test_adapter_c_seed_trailing():
    sig = parse_header("unsigned int luaS_hash(const char *str, size_t l, unsigned int seed);")[0]
    h = SimpleNamespace(algorithm="luaS_hash", category="hash", seed=5, seed_trailing=True)
    body = _resolve_checksum_c(h, "cref", {"luaS_hash": sig}, "u32")
    assert "data.as_ptr(), data.len() as _, 5 as _" in body


def test_adapter_c_seed_first_unchanged():
    sig = parse_header("unsigned long adler32(unsigned long a, const unsigned char *buf, unsigned int len);")[0]
    h = SimpleNamespace(algorithm="adler32", category="checksum", seed=1, seed_trailing=False)
    body = _resolve_checksum_c(h, "cref", {"adler32": sig}, "u32")
    assert "1 as _, data.as_ptr(), data.len() as _" in body
