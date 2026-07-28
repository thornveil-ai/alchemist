"""Generate proptest harnesses that differentially test Rust vs a C reference.

For each algorithm Alchemist extracts, this emits:

  - Standards-based fixed test vectors (from alchemist.standards).
  - A category-specific proptest block:
      * checksum / hash  → byte-exact output comparison
      * cipher           → encrypt(C) → decrypt(Rust) == plaintext, CAVP vectors
      * compression      → roundtrip equivalence, C↔Rust interop
      * filter / control → ULP-bounded numeric equality
      * data_structure / utility → smoke calls only (explicitly opted in —
        the ONLY categories where a no-comparison harness is acceptable)
      * anything else    → an "unverifiable" harness that FAILS. A category
        with no verifying comparator must fail the differential gate, not
        silently pass a smoke check. The weakest check is never the default.

The result is written to a test crate's `tests/differential.rs`. The FFI
crate (see auto_ffi.py) is expected to already provide the C wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent, indent

from alchemist.standards import TestVector, lookup_test_vectors


# ---------------------------------------------------------------------------
# Harness config
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "checksum", "hash", "cipher", "compression", "decompression",
    "filter", "controller", "transform", "data_structure",
    "protocol", "scheduler", "utility", "other", "scalar", "inplace", "scalar_mutator",
    "cipher_seq", "block_cipher", "alloc_seq", "hash_seq", "hash_digest_seq", "cbuf_out", "cstr_out", "buf_transform",
    "iarray_reduce", "cstr_scalar", "buf_gen", "cstr_roundtrip"}


@dataclass
class AlgorithmHarness:
    """One algorithm to differentially test.

    All expressions are snippets that appear inside a test function body.
    `rust_call` is a Rust expression that takes `&input` and returns the output.
    `c_call` is the corresponding C-wrapper invocation.
    For ciphers and roundtrips, extra call points (decrypt/decompress) are
    configured via the optional fields.
    """
    algorithm: str
    category: str
    rust_call: str       # e.g. "zlib_checksum::Adler32::compute(1, &input, input.len())"
    c_call: str          # e.g. "c_ref::c_adler32(&input)"
    # For ciphers / round-tripping pairs:
    rust_decrypt_call: str | None = None    # takes `&ct`, `&key` → plaintext
    c_decrypt_call: str | None = None
    rust_decompress_call: str | None = None  # takes `&compressed`, `orig_len` → Vec<u8>
    c_decompress_call: str | None = None
    # For floating-point tolerance
    ulp_tolerance: int = 0
    # Standard initial value for checksum-style APIs (Adler-32 seeds at 1,
    # CRC-32 at 0). adapter_gen bakes this into both the C and Rust wrappers
    # so the two sides are seeded identically.
    seed: int | None = None
    # True when the seed is the TRAILING arg (`hash(data, len, seed)`, e.g. Lua
    # luaS_hash / FNV / murmur) rather than the leading one (adler32). adapter_gen
    # places the baked seed accordingly on both sides.
    seed_trailing: bool = False
    # Byte-digest hash (SipHash / SHA / HMAC family): output is a Vec<u8>
    # digest, not a scalar. adapter_gen emits Vec<u8>-returning wrappers and
    # the harness compares digest bytes. `key` (canonical, or None if
    # unkeyed) and `digest_len` are baked into both wrappers.
    digest: bool = False
    key: bytes | None = None
    state_rust: str | None = None
    mutator_bind: str | None = None
    mutator_arg_types: list | None = None
    seq_struct: str | None = None
    seq_init: str | None = None
    seq_gen: str | None = None
    # Cipher init has a trailing drop-N param (WjCryptLib RC4). adapter_gen passes 0.
    seq_init_drop: bool = False
    # Block-cipher key-schedule carrier: "struct" (Blowfish) or "array" (AES WORD w[]).
    bc_carrier: str = "struct"
    bc_words: int = 0  # array-carrier: number of WORD round-key slots to allocate
    init_kinds: list | None = None
    # Hash-sequence (init; update(data); final() -> digest): the state primitive is
    # `state_rust`, `seq_init`/`seq_gen` name the init/update fns, `hash_ret` the digest type.
    hash_ret: str | None = None
    # Multi-arg scalar function: rust types of each by-value arg (a0, a1, ...).
    scalar_arg_types: list | None = None
    digest_len: int = 8
    # Input lengths at algorithmic fold boundaries (NMAX block edges, word/
    # braid alignment, batch thresholds). Random sampling rarely lands
    # exactly on these; each gets a deterministic differential test.
    boundary_lengths: list[int] = field(default_factory=list)
    # Override input strategy — defaults per category
    input_strategy: str | None = None
    # For DECODERS: a C-encoder call (e.g. "c_smaz_compress(&pt)") used to mint
    # a VALID stream from random plaintext `pt` before decoding, so the C
    # decoder never walks off a malformed frame (UB) that safe Rust can't match.
    encoder_c_call: str | None = None
    # Additional imports required in the emitted harness
    extra_imports: list[str] = field(default_factory=list)
    # Upper proptest case count
    cases: int = 1024


DEFAULT_IMPORTS = [
    "use proptest::prelude::*;",
]


# ---------------------------------------------------------------------------
# Per-category block templates
# ---------------------------------------------------------------------------

def _fixed_vectors_block(h: AlgorithmHarness) -> str:
    """Emit #[test] fns for every standards vector (exact match).

    Only emits if standards catalog has entries for this algorithm.
    """
    vectors = lookup_test_vectors(h.algorithm)
    if not vectors:
        return ""
    body = []
    body.append(f"// Fixed test vectors for {h.algorithm} from alchemist.standards catalog.")
    for i, v in enumerate(vectors):
        if h.category in ("checksum", "hash"):
            body.append(_fixed_digest_test(h, v, i))
        elif h.category == "cipher":
            body.append(_fixed_cipher_test(h, v, i))
        elif h.category in ("compression", "decompression"):
            body.append(_fixed_roundtrip_test(h, v, i))
        else:
            body.append(_fixed_generic_test(h, v, i))
    return "\n\n".join(b for b in body if b)


def _fixed_digest_test(h: AlgorithmHarness, v: TestVector, idx: int) -> str:
    fn_name = f"fixed_{h.algorithm}_{_slug(v.name) or idx}"
    input_lit = v.as_rust_literal("input")
    expected = v.expected_hex
    # For checksum: expected is 32-bit. For hash: expected is arbitrary digest bytes.
    if h.category == "checksum":
        return dedent(f"""\
            #[test]
            fn {fn_name}() {{
                let input: &[u8] = {input_lit};
                let rust_out = {h.rust_call};
                assert_eq!(format!("{{:08x}}", rust_out), "{expected}",
                    "standards vector {v.name!r} failed");
            }}
        """).rstrip()
    # hash: hex match
    return dedent(f"""\
        #[test]
        fn {fn_name}() {{
            let input: &[u8] = {input_lit};
            let digest = {h.rust_call};
            let hex: String = digest.iter().map(|b| format!("{{:02x}}", b)).collect();
            assert_eq!(hex, "{expected}", "standards vector {v.name!r} failed");
        }}
    """).rstrip()


def _fixed_cipher_test(h: AlgorithmHarness, v: TestVector, idx: int) -> str:
    fn_name = f"fixed_{h.algorithm}_{_slug(v.name) or idx}"
    input_lit = v.as_rust_literal("input")
    key_lit = v.as_rust_literal("key")
    expected_lit = v.as_rust_literal("expected")
    return dedent(f"""\
        #[test]
        fn {fn_name}() {{
            let input: &[u8] = {input_lit};
            let key: &[u8] = {key_lit};
            let expected: &[u8] = {expected_lit};
            let ct = {h.rust_call};
            assert_eq!(ct.as_slice(), expected, "cipher vector {v.name!r} encrypt failed");
        }}
    """).rstrip()


def _fixed_roundtrip_test(h: AlgorithmHarness, v: TestVector, idx: int) -> str:
    fn_name = f"fixed_{h.algorithm}_{_slug(v.name) or idx}"
    input_lit = v.as_rust_literal("input")
    # For compression: we check decompress-compatibility with known-good blob
    expected_lit = v.as_rust_literal("expected")
    if not h.rust_decompress_call:
        return ""
    # Bind the names the decompress expression expects (`compressed`, `input`)
    # so the same call string compiles here and in the proptest blocks.
    return dedent(f"""\
        #[test]
        fn {fn_name}() {{
            let original: &[u8] = {input_lit};
            let reference_compressed: &[u8] = {expected_lit};
            let input = original.to_vec();
            let compressed = reference_compressed.to_vec();
            let (status, decompressed) = {h.rust_decompress_call};
            assert_eq!(status, 0,
                "decompress of standards blob {v.name!r} reported failure");
            assert_eq!(decompressed.as_slice(), original,
                "decompress of standards blob {v.name!r} did not recover input");
        }}
    """).rstrip()


def _fixed_generic_test(h: AlgorithmHarness, v: TestVector, idx: int) -> str:
    fn_name = f"fixed_{h.algorithm}_{_slug(v.name) or idx}"
    input_lit = v.as_rust_literal("input")
    return dedent(f"""\
        #[test]
        fn {fn_name}() {{
            let input: &[u8] = {input_lit};
            let _ = {h.rust_call};
        }}
    """).rstrip()


# ----- Proptest blocks -----

# Categories where a smoke-only harness is an explicit, documented choice.
# Smoke calls the Rust side and discards the result — it verifies nothing
# about equivalence. It must never be reachable by fall-through.
SMOKE_CATEGORIES = {"data_structure", "utility"}


def _proptest_block(h: AlgorithmHarness) -> str:
    if h.digest:
        return _proptest_bytes_digest_block(h)
    if h.category in ("checksum", "hash"):
        return _proptest_digest_block(h)
    if h.category == "cipher":
        return _proptest_cipher_block(h)
    if h.category == "scalar":
        return _proptest_scalar_block(h)
    if h.category == "scalar_mutator":
        return _proptest_scalar_mutator_block(h)
    if h.category == "cipher_seq":
        return _proptest_cipher_seq_block(h)
    if h.category == "block_cipher":
        return _proptest_block_cipher(h)
    if h.category == "alloc_seq":
        return _proptest_alloc_seq_block(h)
    if h.category == "hash_seq":
        return _proptest_hash_seq_block(h)
    if h.category == "hash_digest_seq":
        return _proptest_hash_digest_seq_block(h)
    if h.category == "buf_transform":
        return _proptest_buf_transform_block(h)
    if h.category == "cbuf_out":
        return _proptest_cbuf_out_block(h)
    if h.category == "cstr_out":
        return _proptest_cstr_out_block(h)
    if h.category == "iarray_reduce":
        return _proptest_iarray_reduce_block(h)
    if h.category == "cstr_scalar":
        return _proptest_cstr_scalar_block(h)
    if h.category == "buf_gen":
        return _proptest_buf_gen_block(h)
    if h.category == "cstr_roundtrip":
        return _proptest_cstr_roundtrip_block(h)
    if h.category == "inplace":
        return _proptest_inplace_block(h)
    if h.category in ("compression", "decompression"):
        return _proptest_compression_block(h)
    if h.category in ("filter", "controller"):
        return _proptest_float_block(h)
    if h.category in SMOKE_CATEGORIES:
        return _proptest_smoke_block(h)
    # Recognized category with no verifying comparator (transform, protocol,
    # scheduler, other, ...). Emitting a smoke check here would let the
    # differential gate pass without ever consulting the C reference — the
    # exact false-green this pipeline exists to prevent. Fail closed instead.
    return _proptest_unverifiable_block(h)


def _boundary_block(h: AlgorithmHarness) -> str:
    """Deterministic differential test at algorithmic fold boundaries.

    Random length sampling almost never lands exactly on NMAX block edges,
    word alignments, or batch thresholds — the places where accumulator
    folding and braid paths switch. Content is a fixed LCG so failures
    reproduce byte-for-byte.
    """
    if not h.boundary_lengths:
        return ""
    lengths = ", ".join(str(n) for n in h.boundary_lengths)
    return dedent(f"""\
        #[test]
        fn {h.algorithm}_boundary_lengths_match_c_reference() {{
            let lengths: &[usize] = &[{lengths}];
            let mut state: u64 = 0x415f_435f_5f42_4459; // fixed seed — reproducible
            for &len in lengths {{
                let mut input = vec![0u8; len];
                for b in input.iter_mut() {{
                    state = state
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (state >> 33) as u8;
                }}
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                assert_eq!(rust_out, c_out,
                    "{h.algorithm} diverged from C reference at boundary length {{}}", len);
            }}
        }}
    """).rstrip()


def _proptest_buf_transform_block(h: AlgorithmHarness) -> str:
    """Differential for a variable-length buffer transform (codec): fuzz an input byte buffer
    and compare the two output byte vectors (Rust `(&[u8])->Vec<u8>` vs the C out[0..ret]).

    For a DECODER (h.encoder_c_call set), the fuzzed bytes are random PLAINTEXT
    that we first run through the C encoder to obtain a valid stream — decoding
    random bytes would exercise the C decoder's undefined behavior on malformed
    input, which a memory-safe Rust translation cannot (and must not) replicate."""
    strategy = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..512)"
    if h.encoder_c_call:
        return dedent(f"""\
            proptest! {{
                #![proptest_config(ProptestConfig::with_cases({h.cases}))]

                #[test]
                fn {h.algorithm}_matches_c_reference(pt in {strategy}) {{
                    // Mint a VALID encoded stream from random plaintext, then decode it.
                    let input = {h.encoder_c_call};
                    prop_assert_eq!({h.rust_call}, {h.c_call});
                }}
            }}
        """).rstrip()
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(input in {strategy}) {{
                prop_assert_eq!({h.rust_call}, {h.c_call});
            }}
        }}
    """).rstrip()


def _proptest_cstr_roundtrip_block(h: AlgorithmHarness) -> str:
    """Differential for a DECODER `(&str) -> Vec<u8>` verified by the roundtrip
    identity: mint a VALID encoded stream from random plaintext via the C
    ENCODER (`encoder_c_call`, the reference), then require the Rust decoder to
    invert it byte-exactly — `decode(encode(pt)) == pt`. The C decoder's own
    `char*` return is NUL-lossy for binary output, so it is never called; the
    encoder is the oracle. Decoding random (un-encoded) bytes would exercise the
    C decoder's UB-on-malformed-input, which memory-safe Rust cannot replicate."""
    strategy = h.input_strategy or "prop::collection::vec(1u8..=127u8, 0..48)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_roundtrip_matches_c_reference(pt in {strategy}) {{
                // Mint a valid encoded stream from random plaintext via the C
                // encoder, then require the Rust decoder to recover it exactly.
                let input = {h.encoder_c_call};
                let rust_out = {h.rust_call};
                prop_assert_eq!(rust_out.as_slice(), pt.as_slice());
            }}
        }}
    """).rstrip()


def _proptest_cbuf_out_block(h: AlgorithmHarness) -> str:
    """Differential for a C-string-in -> result-string-out fn (NMEA): fuzz a printable
    ASCII string (no interior NUL — CString rejects it) that exercises the '$' start marker
    and the '*'/CR/LF terminators, and compare the two result strings."""
    strategy = h.input_strategy or r'"[A-Za-z0-9,.$*\r\n-]{0,40}"'
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(input in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_cstr_out_block(h: AlgorithmHarness) -> str:
    """Differential for a `char* f(char*)` text transform (to_upper/rot13/hex_encode):
    fuzz a printable-ASCII string (no interior NUL — CString rejects it; the range
    spans lowercase AND uppercase so case-changing transforms are actually exercised)
    and compare the two result strings."""
    strategy = h.input_strategy or r'"[ -~]{0,48}"'
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(input in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_iarray_reduce_block(h: AlgorithmHarness) -> str:
    """Differential for an int-array reduction `(&[T]) -> R`: fuzz a bounded-value
    array of the element type (bounds keep the C reduction free of signed-overflow
    UB) and compare the scalar result."""
    elem = h.state_rust or "i32"
    strategy = h.input_strategy or f"prop::collection::vec(any::<{elem}>(), 0..64)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(input in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_cstr_scalar_block(h: AlgorithmHarness) -> str:
    """Differential for `<scalar> f(const char* s, ...scalars)`: fuzz a printable
    string plus each extra scalar arg and compare the scalar result. The Rust and C
    wrappers take `(&str, ...)`, so `input` is bound to `(s, a0, a1, ...)`."""
    extras = h.scalar_arg_types or []
    names = ["s"] + [f"a{i}" for i in range(len(extras))]
    parts = ['"[ -~]{0,48}"'] + [f"any::<{t}>()" for t in extras]
    if len(names) == 1:
        bind, strat = "s", parts[0]
    else:
        bind = "(" + ", ".join(names) + ")"
        strat = "(" + ", ".join(parts) + ")"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference({bind} in {strat}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_buf_gen_block(h: AlgorithmHarness) -> str:
    """Differential for a buffer generator `(usize, ...scalars) -> Vec<u8>`: fuzz a
    small length + each scalar arg and compare the two generated byte vectors."""
    extras = h.scalar_arg_types or []
    names = ["n"] + [f"a{i}" for i in range(len(extras))]
    parts = ["0usize..64"] + [f"any::<{t}>()" for t in extras]
    bind = "(" + ", ".join(names) + ")" if len(names) > 1 else names[0]
    strat = "(" + ", ".join(parts) + ")" if len(parts) > 1 else parts[0]
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference({bind} in {strat}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_inplace_block(h: AlgorithmHarness) -> str:
    """Differential for an in-place byte transform: fuzz a buffer, compare Rust vs C."""
    strategy = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..256)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(input in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_alloc_seq_block(h: AlgorithmHarness) -> str:
    """Whole-crate allocator sequence differential: init(buffer of size cap) then op*."""
    strat = h.input_strategy or "(0usize..256, prop::collection::vec(0usize..300, 1..8))"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference((cap, ns) in {strat}) {{
                prop_assert_eq!(rust_{h.algorithm}(cap, ns.clone()), c_{h.algorithm}(cap, ns));
            }}
        }}
    """).rstrip()


def _proptest_cipher_seq_block(h: AlgorithmHarness) -> str:
    """Whole-crate cipher sequence differential: init(key) then keystream(out), compare bytes."""
    strat = h.input_strategy or "(prop::collection::vec(any::<u8>(), 1..64), 0usize..256)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference((key, outlen) in {strat}) {{
                prop_assert_eq!(rust_{h.algorithm}(key.clone(), outlen), c_{h.algorithm}(key, outlen));
            }}
        }}
    """).rstrip()


def _proptest_block_cipher(h: AlgorithmHarness) -> str:
    """Block-cipher differential: key_setup(key) then encrypt(one block), compare bytes."""
    strat = h.input_strategy or (
        "(prop::collection::vec(any::<u8>(), 1..56), "
        "prop::collection::vec(any::<u8>(), 8..=8))")
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference((key, block) in {strat}) {{
                prop_assert_eq!(rust_{h.algorithm}(key.clone(), block.clone()), c_{h.algorithm}(key, block));
            }}
        }}
    """).rstrip()


def _proptest_hash_seq_block(h: AlgorithmHarness) -> str:
    """Whole-crate hash sequence differential: init; update(data); final() -> digest, compare."""
    strat = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..128)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(data in {strat}) {{
                prop_assert_eq!(rust_{h.algorithm}(data.clone()), c_{h.algorithm}(data));
            }}
        }}
    """).rstrip()


def _proptest_hash_digest_seq_block(h: AlgorithmHarness) -> str:
    """Context-hash digest sequence differential (SHA-256/SHA-1/MD5): fuzz the
    message, run the whole init->update->final sequence on BOTH the Rust port and
    the compiled-C reference, and compare the N-byte digest byte-exactly."""
    strat = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..512)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_digest_matches_c_reference(data in {strat}) {{
                prop_assert_eq!({h.rust_call}, {h.c_call});
            }}
        }}
    """).rstrip()


def _proptest_scalar_mutator_block(h: AlgorithmHarness) -> str:
    """Differential for a scalar-state mutator: fuzz the initial state, compare (ret, post)."""
    strategy = h.input_strategy or "any::<u64>()"
    bind = h.mutator_bind or "input"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference({bind} in {strategy}) {{
                prop_assert_eq!({h.rust_call}, {h.c_call});
            }}
        }}
    """).rstrip()


def _proptest_scalar_block(h: AlgorithmHarness) -> str:
    """Differential for an all-scalar function (any arity): fuzz the args, compare Rust vs C."""
    strategy = h.input_strategy or "any::<u64>()"
    bind = h.mutator_bind or "a0"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference({bind} in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_digest_block(h: AlgorithmHarness) -> str:
    strategy = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..8192)"
    blocks = [dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_matches_c_reference(input in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()]
    boundary = _boundary_block(h)
    if boundary:
        blocks.append(boundary)
    return "\n\n".join(blocks)


def _proptest_bytes_digest_block(h: AlgorithmHarness) -> str:
    """Byte-digest hash: wrappers return the Vec<u8> digest; compare bytes.

    The wrappers (adapter_gen) bake in the key and digest length, so the
    harness fuzzes only the message.
    """
    strategy = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..8192)"
    blocks = [dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_digest_matches_c_reference(input in {strategy}) {{
                let rust_out: Vec<u8> = {h.rust_call};
                let c_out: Vec<u8> = {h.c_call};
                prop_assert_eq!(rust_out, c_out);
            }}
        }}
    """).rstrip()]
    # Boundary lengths for digests: content-varied fixed lengths.
    if h.boundary_lengths:
        lengths = ", ".join(str(n) for n in h.boundary_lengths)
        blocks.append(dedent(f"""\
            #[test]
            fn {h.algorithm}_digest_boundary_lengths() {{
                let lengths: &[usize] = &[{lengths}];
                let mut state: u64 = 0x415f_435f_5f42_4459;
                for &len in lengths {{
                    let mut input = vec![0u8; len];
                    for b in input.iter_mut() {{
                        state = state
                            .wrapping_mul(6364136223846793005)
                            .wrapping_add(1442695040888963407);
                        *b = (state >> 33) as u8;
                    }}
                    let rust_out: Vec<u8> = {h.rust_call};
                    let c_out: Vec<u8> = {h.c_call};
                    assert_eq!(rust_out, c_out,
                        "{h.algorithm} digest diverged from C at length {{}}", len);
                }}
            }}
        """).rstrip())
    return "\n\n".join(blocks)


def _proptest_cipher_block(h: AlgorithmHarness) -> str:
    if not h.rust_decrypt_call or not h.c_decrypt_call:
        # Without decrypt, at least ensure forward pass matches C ciphertext
        return dedent(f"""\
            proptest! {{
                #![proptest_config(ProptestConfig::with_cases({h.cases}))]

                #[test]
                fn {h.algorithm}_encrypt_matches_c(
                    input in prop::collection::vec(any::<u8>(), 16..16),
                    key in prop::collection::vec(any::<u8>(), 16..16),
                ) {{
                    let rust_ct = {h.rust_call};
                    let c_ct = {h.c_call};
                    prop_assert_eq!(rust_ct.as_slice(), c_ct.as_slice());
                }}
            }}
        """).rstrip()
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_roundtrip(
                input in prop::collection::vec(any::<u8>(), 16..16),
                key in prop::collection::vec(any::<u8>(), 16..16),
            ) {{
                // Rust encrypt → Rust decrypt
                let ct = {h.rust_call};
                let pt = {h.rust_decrypt_call};
                prop_assert_eq!(pt.as_slice(), input.as_slice());
            }}

            #[test]
            fn {h.algorithm}_interop_rust_encrypt_c_decrypt(
                input in prop::collection::vec(any::<u8>(), 16..16),
                key in prop::collection::vec(any::<u8>(), 16..16),
            ) {{
                let ct = {h.rust_call};
                let pt = {h.c_decrypt_call};
                prop_assert_eq!(pt.as_slice(), input.as_slice());
            }}
        }}
    """).rstrip()


def _proptest_compression_block(h: AlgorithmHarness) -> str:
    """Full effect-footprint compression harness.

    Wrapper contract (emitted by adapter_gen): compress expressions evaluate
    to `(i32, Vec<u8>)` given `input: Vec<u8>`; decompress expressions
    evaluate to `(i32, Vec<u8>)` given `compressed: Vec<u8>` and `input`.
    Status is part of the footprint: a side that "succeeds" where the
    reference fails (the compress-returns-zeros failure class) is caught by
    the parity test even when no roundtrip runs. Compressed bytes are NOT
    compared byte-for-byte — DEFLATE permits multiple valid encodings — so
    equivalence is: status parity + roundtrip recovery + cross-interop.
    """
    strategy = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..8192)"
    rust_decomp = h.rust_decompress_call or ""
    c_decomp = h.c_decompress_call or ""
    blocks = []
    # 0. Status parity — success/failure must agree on identical inputs.
    #    (Exact error-code parity needs an error-enum mapping that isn't
    #    discoverable from the generated API yet; success parity already
    #    kills silent-stub "successes".)
    if h.c_call:
        blocks.append(dedent(f"""\
            #[test]
            fn {h.algorithm}_status_parity(input in {strategy}) {{
                let (rust_status, _rust_bytes) = {h.rust_call};
                let (c_status, _c_bytes) = {h.c_call};
                prop_assert_eq!(rust_status == 0, c_status == 0,
                    "success disagreement: rust_status={{}}, c_status={{}}",
                    rust_status, c_status);
            }}
        """).rstrip())
    # 1. Rust roundtrip
    if rust_decomp:
        blocks.append(dedent(f"""\
            #[test]
            fn {h.algorithm}_rust_roundtrip(input in {strategy}) {{
                let (c_status, compressed) = {h.rust_call};
                prop_assert_eq!(c_status, 0, "rust compress failed: {{}}", c_status);
                let (d_status, decompressed) = {rust_decomp};
                prop_assert_eq!(d_status, 0, "rust decompress failed: {{}}", d_status);
                prop_assert_eq!(decompressed.as_slice(), input.as_slice());
            }}
        """).rstrip())
    # 2. Rust compress → C decompress
    if c_decomp:
        blocks.append(dedent(f"""\
            #[test]
            fn {h.algorithm}_rust_compress_c_decompress(input in {strategy}) {{
                let (c_status, compressed) = {h.rust_call};
                prop_assert_eq!(c_status, 0, "rust compress failed: {{}}", c_status);
                let (d_status, decompressed) = {c_decomp};
                prop_assert_eq!(d_status, 0, "C decompress rejected rust output: {{}}", d_status);
                prop_assert_eq!(decompressed.as_slice(), input.as_slice());
            }}
        """).rstrip())
    # 3. C compress → Rust decompress (requires both c_call and rust_decompress_call)
    if rust_decomp and h.c_call:
        blocks.append(dedent(f"""\
            #[test]
            fn {h.algorithm}_c_compress_rust_decompress(input in {strategy}) {{
                let (c_status, compressed) = {h.c_call};
                prop_assert_eq!(c_status, 0, "C compress failed: {{}}", c_status);
                let (d_status, decompressed) = {rust_decomp};
                prop_assert_eq!(d_status, 0, "rust decompress rejected C output: {{}}", d_status);
                prop_assert_eq!(decompressed.as_slice(), input.as_slice());
            }}
        """).rstrip())
    if not blocks:
        return ""
    joined = "\n\n".join(indent(b, "    ") for b in blocks)
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

        """).rstrip() + "\n" + joined + "\n}"


def _proptest_float_block(h: AlgorithmHarness) -> str:
    strategy = h.input_strategy or "prop::collection::vec(any::<f64>().prop_filter(\"finite\", |f| f.is_finite()), 1..256)"
    ulp = h.ulp_tolerance
    return dedent(f"""\
        fn within_ulps(a: f64, b: f64, ulps: i64) -> bool {{
            if a == b {{ return true; }}
            if a.is_nan() || b.is_nan() {{ return false; }}
            let ua = a.to_bits() as i64;
            let ub = b.to_bits() as i64;
            (ua - ub).abs() <= ulps
        }}

        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_within_ulp_tolerance(input in {strategy}) {{
                let rust_out = {h.rust_call};
                let c_out = {h.c_call};
                prop_assert!(within_ulps(rust_out, c_out, {ulp}),
                    "rust={{}}, c={{}}", rust_out, c_out);
            }}
        }}
    """).rstrip()


def _proptest_unverifiable_block(h: AlgorithmHarness) -> str:
    """Emit a harness that always fails: this algorithm cannot be verified.

    Categories without a verifying comparator get a #[test] that panics with
    an explanation instead of a smoke check that would vacuously pass. The
    differential gate stays red until someone either assigns a verifiable
    category or writes a real comparator for this one.
    """
    return dedent(f"""\
        #[test]
        fn {h.algorithm}_unverifiable() {{
            panic!(
                "UNVERIFIABLE: algorithm '{h.algorithm}' has category '{h.category}', \\
        which has no differential comparator. Refusing to emit a smoke-only check \\
        that would pass without consulting the C reference. Assign a verifiable \\
        category (checksum, hash, cipher, compression, filter) or add a comparator \\
        for '{h.category}' to alchemist/verifier/proptest_gen.py."
            );
        }}
    """).rstrip()


def _proptest_smoke_block(h: AlgorithmHarness) -> str:
    strategy = h.input_strategy or "prop::collection::vec(any::<u8>(), 0..256)"
    return dedent(f"""\
        proptest! {{
            #![proptest_config(ProptestConfig::with_cases({h.cases}))]

            #[test]
            fn {h.algorithm}_smoke(input in {strategy}) {{
                let _ = {h.rust_call};
            }}
        }}
    """).rstrip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slug(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_/":
            out.append("_")
    slug = "".join(out).strip("_")
    # Collapse multiple underscores
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug


def emit_differential_test(
    harnesses: list[AlgorithmHarness],
    *,
    extra_imports: list[str] | None = None,
    module_doc: str | None = None,
    include_catalog_kats: bool = True,
) -> str:
    """Emit a full `tests/differential.rs` file for a list of harnesses.

    `include_catalog_kats=False` suppresses the standards-catalog fixed known-answer tests —
    correct for an AUTO-ORACLE differential where the subject's OWN compiled C is the ground
    truth: a canonical CRC/hash KAT is WRONG for a custom variant of that family (e.g. libcrc's
    SHT75 CRC-8 vs canonical CRC-8) and would fail a byte-exact-correct translation."""
    imports: list[str] = list(DEFAULT_IMPORTS)
    for h in harnesses:
        imports.extend(h.extra_imports)
    if extra_imports:
        imports.extend(extra_imports)
    # Dedup while preserving order
    seen: set[str] = set()
    unique_imports: list[str] = []
    for imp in imports:
        if imp not in seen:
            seen.add(imp)
            unique_imports.append(imp)

    lines: list[str] = []
    if module_doc:
        for l in module_doc.splitlines():
            lines.append(f"//! {l}")
        lines.append("")
    lines.extend(unique_imports)
    lines.append("")

    for h in harnesses:
        if h.category not in VALID_CATEGORIES:
            raise ValueError(f"Unknown category for {h.algorithm}: {h.category}")
        lines.append(f"// === {h.algorithm} ({h.category}) ===")
        block = _fixed_vectors_block(h) if include_catalog_kats else ""
        if block:
            lines.append(block)
            lines.append("")
        lines.append(_proptest_block(h))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_differential_test(
    harnesses: list[AlgorithmHarness],
    output_path: Path,
    *,
    module_doc: str | None = None,
) -> Path:
    """Emit and write a differential test file; returns the path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    src = emit_differential_test(harnesses, module_doc=module_doc)
    output_path.write_text(src, encoding="utf-8")
    return output_path
