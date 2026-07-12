"""Auto-generate a DifferentialConfig + fuzz bindings for any subject.

zlib has a hand-curated config (zlib_config.py). Every other subject used to
hit "no differential config provided — REFUSING to claim success", which is
honest but leaves the gate unreachable. This module derives the config from
what the subject itself declares:

  - C sources:      every non-test .c in the subject dir → the oracle DLL.
  - C signatures:   parsed from the subject's headers (auto_ffi.parse_header).
  - Harnesses:      one per spec algorithm whose category is checksum/hash
                    AND whose C export matches a canonical byte-slice shape.
  - Fuzz bindings:  ctypes CFunctionBinding per matched export, so Phase B
                    can mint oracle-backed vectors for functions the
                    standards catalog doesn't know.

Anything that doesn't match a recognized shape is simply not configured —
and an unconfigured algorithm cannot pass, because the differential gate
requires a harness and the anti-stub/test gates still see its stubs. The
weakest check is never the default.

Shape catalog (C side):
  seeded byte-slice:   (int seed, const u8*, len)  -> int     e.g. adler32
  unseeded byte-slice: (const u8*, len)            -> int     e.g. fletcher16
"""

from __future__ import annotations

import ctypes
import re
from dataclasses import dataclass
from pathlib import Path

from alchemist.extractor.fuzz_vectors import CFunctionBinding
from alchemist.verifier.auto_ffi import CSignature, TypedefMap, parse_header
from alchemist.verifier.differential_tester import DifferentialConfig
from alchemist.verifier.proptest_gen import AlgorithmHarness

from alchemist.verifier import struct_lift  # noqa: E402

_INT_C_TYPES = re.compile(
    r"^(unsigned|unsigned int|unsigned long|unsigned short|int|long|"
    r"uint8_t|uint16_t|uint32_t|uint64_t|size_t|uInt|uLong|z_size_t)$"
)
_BYTE_PTR = re.compile(r"^(const\s+)?(unsigned char|uint8_t|Bytef|u_char|char)\s*\*$")
# A read-only byte/opaque input pointer (hash APIs often take `const void *`).
_CONST_IN_PTR = re.compile(
    r"^const\s+(unsigned char|uint8_t|Bytef|u_char|void)\s*\*$")
# A writable output byte buffer.
_MUT_BYTE_PTR = re.compile(r"^(unsigned char|uint8_t|u_char)\s*\*$")
_SIZE_T = re.compile(r"^(const\s+)?(size_t|z_size_t|unsigned long|uInt|uLong)$")
# A NUL-terminated C string pointer: `char*` / `const char*` / `unsigned char*`.
_CHAR_PTR = re.compile(r"^(const\s+)?(unsigned\s+)?char\s*\*$")

# Canonical key length for keyed digests whose C reads a fixed-size key with
# no length parameter (SipHash reads 16 bytes). Overridable per subject.
_DEFAULT_KEY_LEN = 16
# Canonical digest length to probe when `outlen` is a runtime parameter.
_DEFAULT_DIGEST_LEN = 8

_CTYPE_FOR: dict[str, type] = {
    "uint8_t": ctypes.c_uint8,
    "uint16_t": ctypes.c_uint16,
    "uint32_t": ctypes.c_uint32,
    "uint64_t": ctypes.c_uint64,
    "unsigned": ctypes.c_uint,
    "unsigned int": ctypes.c_uint,
    "unsigned long": ctypes.c_ulong,
    "unsigned short": ctypes.c_ushort,
    "int": ctypes.c_int,
    "long": ctypes.c_long,
    "size_t": ctypes.c_size_t,
    "z_size_t": ctypes.c_size_t,
    "uInt": ctypes.c_uint,
    "uLong": ctypes.c_ulong,
    "unsigned char": ctypes.c_ubyte,
    "signed char": ctypes.c_byte,
    "char": ctypes.c_ubyte,
    "short": ctypes.c_short,
    "unsigned long long": ctypes.c_ulonglong,
    "long long": ctypes.c_longlong,
    "int8_t": ctypes.c_int8,
    "int16_t": ctypes.c_int16,
    "int32_t": ctypes.c_int32,
    "int64_t": ctypes.c_int64,
    "ssize_t": ctypes.c_ssize_t,
}

# Any integer/char scalar as a by-value ARGUMENT (no pointer). Broader than
# _INT_C_TYPES (which is used for length params) — it also admits char/short and
# fixed-width signed types, so a pure multi-scalar function like
# update_crc(uint32_t, unsigned char) -> uint32_t is differentiable.
_SCALAR_ARG = re.compile(
    r"^(unsigned char|signed char|char|unsigned short|short|unsigned int|unsigned long long|"
    r"unsigned long|unsigned|int|long long|long|"
    r"uint8_t|uint16_t|uint32_t|uint64_t|int8_t|int16_t|int32_t|int64_t|"
    r"size_t|ssize_t|z_size_t|uInt|uLong)$")


def _ctype(c_type: str):
    return _CTYPE_FOR.get(c_type.strip())


def default_seed(name: str) -> int:
    """Standard initial value by checksum family. Adler-32 (RFC 1950) seeds
    at 1; CRC-32 and the rest of the reflected-register family seed at 0."""
    return 1 if "adler" in name.lower() else 0


def classify_checksum_shape(sig: CSignature) -> str | None:
    """'seeded' | 'unseeded' | None for unrecognized."""
    params = [t.strip() for _, t in sig.params]
    if not _ctype(sig.return_type or ""):
        return None
    if (len(params) == 3 and _INT_C_TYPES.match(params[0])
            and _BYTE_PTR.match(params[1]) and _INT_C_TYPES.match(params[2])):
        return "seeded"
    # Seed as the TRAILING arg: `hash(const char* data, size_t len, unsigned seed)`.
    # Very common (Lua luaS_hash, FNV/murmur variants). Same info as "seeded",
    # only the seed position differs — handled by seed_trailing downstream.
    if (len(params) == 3 and _BYTE_PTR.match(params[0])
            and _INT_C_TYPES.match(params[1]) and _INT_C_TYPES.match(params[2])):
        return "seeded_trailing"
    if (len(params) == 2 and _BYTE_PTR.match(params[0])
            and _INT_C_TYPES.match(params[1])):
        return "unseeded"
    return None


@dataclass
class DigestShape:
    """Descriptor for a byte-digest hash function.

    C shape: `int f(const IN* in, size inlen, [const KEY* k,] MUT* out, size outlen)`
    Rust shape (as the extractor lifts it): the out buffer becomes the return,
    `fn f(in: &[u8], [k: &[u8],] outlen: usize) -> Result<Vec<u8>, E>`.
    Key and digest length are baked to canonical values for the oracle so the
    whole thing collapses to message -> digest-bytes comparison.
    """
    in_idx: int
    inlen_idx: int
    out_idx: int
    outlen_idx: int
    key_idx: int | None
    key_len: int
    digest_len: int


# Known fixed digest sizes (bytes) by algorithm family — a hash writes a FIXED number of
# bytes regardless of the caller's outlen, so the oracle must bake the right size or it
# truncates (SipHash 8, SHA-256 32, ...). Inferred from the C function name.
_DIGEST_LENS = {
    "sha512_256": 32, "sha512_224": 28, "sha224": 28, "sha256": 32, "sha384": 48,
    "sha512": 64, "sha1": 20, "sha3_256": 32, "sha3_512": 64, "md5": 16, "blake2s": 32,
    "blake2b": 64, "siphash": 8,
}


def _digest_len_for(name: str) -> int:
    """Fixed digest length in bytes for a known hash, else the default. Matches the longest
    family key first (sha512_256 before sha512), then falls back to an embedded bit width."""
    n = (name or "").lower()
    for key in sorted(_DIGEST_LENS, key=len, reverse=True):
        if key in n:
            return _DIGEST_LENS[key]
    m = re.search(r"(128|160|224|256|384|512)", n)
    if m:
        return int(m.group(1)) // 8
    return _DEFAULT_DIGEST_LEN


def classify_digest_shape(sig: CSignature) -> "DigestShape | None":
    """Recognize a byte-digest hash (SipHash / SHA / HMAC family)."""
    if (sig.return_type or "").strip() != "int":
        return None
    types = [t.strip() for _, t in sig.params]
    dlen = _digest_len_for(sig.name)
    # Unkeyed: (const in*, inlen, mut out*, outlen)
    if (len(types) == 4 and _CONST_IN_PTR.match(types[0]) and _SIZE_T.match(types[1])
            and _MUT_BYTE_PTR.match(types[2]) and _SIZE_T.match(types[3])):
        return DigestShape(in_idx=0, inlen_idx=1, out_idx=2, outlen_idx=3,
                           key_idx=None, key_len=0,
                           digest_len=dlen)
    # Keyed: (const in*, inlen, const key*, mut out*, outlen)
    if (len(types) == 5 and _CONST_IN_PTR.match(types[0]) and _SIZE_T.match(types[1])
            and _CONST_IN_PTR.match(types[2]) and _MUT_BYTE_PTR.match(types[3])
            and _SIZE_T.match(types[4])):
        return DigestShape(in_idx=0, inlen_idx=1, out_idx=3, outlen_idx=4,
                           key_idx=2, key_len=_DEFAULT_KEY_LEN,
                           digest_len=dlen)
    return None


# A writable OUTPUT pointer that may be opaque (`void *`) — hash APIs like
# MurmurHash write the digest through a `void *out`.
_ANY_OUT_PTR = re.compile(r"^(unsigned char|uint8_t|u_char|char|void)\s*\*$")
# A read-only INPUT pointer that may be opaque (`const void *key`).
_ANY_IN_PTR = re.compile(r"^(const\s+)?(unsigned char|uint8_t|Bytef|u_char|char|void)\s*\*$")


@dataclass
class HashOutShape:
    """A seeded hash that writes a FIXED-size digest to an output buffer and
    returns void: `void f(const void* in, int len, SCALAR seed, void* out)`.
    The out size is fixed by the function variant (MurmurHash x86_32 -> 4 bytes,
    x64_128 -> 16), inferred from the trailing bit-width in the name.
    Rust shape: `fn f(inp: &[u8], seed: u32) -> Vec<u8>` (the out buffer)."""
    in_idx: int
    inlen_idx: int
    seed_idx: int
    out_idx: int
    out_len: int


def _hash_out_len_for(name: str) -> int:
    """Digest byte-width from the trailing numeric token of a hash name:
    `MurmurHash3_x86_32` -> 32 bits -> 4 bytes; `..._x64_128` -> 16 bytes."""
    toks = re.findall(r"\d+", name or "")
    if toks:
        bits = int(toks[-1])
        if bits in (32, 64, 128, 160, 224, 256, 384, 512):
            return bits // 8
    return 4


def classify_hash_out_shape(sig: CSignature) -> "HashOutShape | None":
    """Recognize `void f(in_ptr, int len, scalar seed, out_ptr)` — a seeded hash
    writing a fixed digest through an output pointer (MurmurHash family)."""
    if (sig.return_type or "").strip() != "void":
        return None
    types = [t.strip() for _, t in sig.params]
    if (len(types) == 4 and _ANY_IN_PTR.match(types[0]) and _INT_C_TYPES.match(types[1])
            and _SCALAR_ARG.match(types[2]) and _ANY_OUT_PTR.match(types[3])):
        return HashOutShape(in_idx=0, inlen_idx=1, seed_idx=2, out_idx=3,
                            out_len=_hash_out_len_for(sig.name))
    return None


def _hash_out_binding(sig: CSignature, desc: HashOutShape) -> CFunctionBinding:
    """Binding whose adapter(fn, data, seed) returns the digest BYTES the C wrote
    to the output buffer."""
    argtypes: list = [None] * len(sig.params)
    argtypes[desc.in_idx] = ctypes.POINTER(ctypes.c_ubyte)
    argtypes[desc.inlen_idx] = _ctype(sig.params[desc.inlen_idx][1]) or ctypes.c_int
    argtypes[desc.seed_idx] = _ctype(sig.params[desc.seed_idx][1]) or ctypes.c_uint
    argtypes[desc.out_idx] = ctypes.POINTER(ctypes.c_ubyte)
    olen = desc.out_len

    def adapter(fn, data: bytes, seed: int = 0):
        in_buf = ((ctypes.c_ubyte * len(data))(*data) if data
                  else ctypes.POINTER(ctypes.c_ubyte)())
        out_buf = (ctypes.c_ubyte * olen)()
        args: list = [None] * len(sig.params)
        args[desc.in_idx] = in_buf
        args[desc.inlen_idx] = len(data)
        args[desc.seed_idx] = seed
        args[desc.out_idx] = out_buf
        fn(*args)
        return bytes(out_buf)

    return CFunctionBinding(c_name=sig.name, restype=None, argtypes=argtypes, adapter=adapter)


def fuzz_hash_out_vectors(dll, alg, sig, *, count: int = 24):
    """Mint {in_bytes, seed} -> digest-bytes vectors for a seeded hash-to-outbuf
    fn from the compiled C oracle. Rust target returns Vec<u8>."""
    from alchemist.extractor.fuzz_vectors import _bytes_to_rust_literal, _gen_byte_inputs, _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    desc = classify_hash_out_shape(sig)
    if desc is None:
        return []
    binding = _hash_out_binding(sig, desc)
    fn = binding.load(dll)
    # Map spec params by Rust type: the byte slice is the message, the u32/scalar is the seed.
    slice_params = [p for p in (alg.inputs or [])
                    if "[u8]" in (p.rust_type or "") or "Vec<u8>" in (p.rust_type or "")]
    scalar_params = [p for p in (alg.inputs or [])
                     if p not in slice_params and any(x in (p.rust_type or "")
                     for x in ("u32", "u64", "i32", "i64", "usize"))]
    if not slice_params:
        return []
    msg_param = slice_params[0].name
    seed_param = scalar_params[0].name if scalar_params else None
    rng = _rng(_FUZZ_SEED)
    inputs = _gen_byte_inputs(rng, count)
    seeds = [0, 1, 0x9747b28c] + [rng.randint(0, 2**32 - 1) for _ in range(count)]
    vectors = []
    for i, data in enumerate(inputs):
        seed = seeds[i % len(seeds)]
        try:
            digest = binding.adapter(fn, bytes(data), seed)
        except Exception:  # noqa: BLE001
            continue
        row = {msg_param: _bytes_to_rust_literal(bytes(data))}
        if seed_param:
            row[seed_param] = f"{seed}u32"
        digest_lit = "vec![" + ", ".join(f"0x{b:02x}" for b in digest) + "]"
        vectors.append(SpecTestVector(
            description=f"fuzz_in{len(data)}_seed{seed}",
            source=f"C reference (hash-out): {sig.name}",
            inputs=row, expected_output=digest_lit, tolerance="exact",
        ))
    return vectors


def canonical_key(key_len: int) -> bytes:
    """Deterministic canonical key: bytes 0x00..0x(len-1). Matches the
    SipHash reference test key and is stable for reproducible oracles."""
    return bytes(range(key_len))


def _digest_binding(sig: CSignature, desc: DigestShape) -> CFunctionBinding:
    """Binding whose adapter(fn, msg) returns the digest BYTES.

    The key (canonical) and outlen (canonical digest_len) are baked in, so
    the fuzz layer sees a plain message -> digest-bytes mapping.
    """
    argtypes: list = [None] * len(sig.params)
    argtypes[desc.in_idx] = ctypes.POINTER(ctypes.c_ubyte)
    argtypes[desc.inlen_idx] = ctypes.c_size_t
    argtypes[desc.out_idx] = ctypes.POINTER(ctypes.c_ubyte)
    argtypes[desc.outlen_idx] = ctypes.c_size_t
    if desc.key_idx is not None:
        argtypes[desc.key_idx] = ctypes.POINTER(ctypes.c_ubyte)
    key = canonical_key(desc.key_len)
    dlen = desc.digest_len

    def adapter(fn, data: bytes):
        in_buf = ((ctypes.c_ubyte * len(data))(*data) if data
                  else ctypes.POINTER(ctypes.c_ubyte)())
        out_buf = (ctypes.c_ubyte * dlen)()
        args: list = [None] * len(sig.params)
        args[desc.in_idx] = in_buf
        args[desc.inlen_idx] = len(data)
        args[desc.out_idx] = out_buf
        args[desc.outlen_idx] = dlen
        if desc.key_idx is not None:
            args[desc.key_idx] = (ctypes.c_ubyte * len(key))(*key)
        rc = int(fn(*args))
        if rc != 0:
            raise RuntimeError(f"{sig.name} returned status {rc}")
        return bytes(out_buf)

    return CFunctionBinding(
        c_name=sig.name, restype=ctypes.c_int, argtypes=tuple(argtypes),
        adapter=adapter,
    )


def _binding_for(sig: CSignature, shape: str, seed: int) -> CFunctionBinding:
    restype = _ctype(sig.return_type)
    if shape == "seeded":
        seed_ct = _ctype(sig.params[0][1]) or ctypes.c_ulong
        len_ct = _ctype(sig.params[2][1]) or ctypes.c_size_t
        argtypes = (seed_ct, ctypes.POINTER(ctypes.c_ubyte), len_ct)

        def adapter(fn, data: bytes, _seed=seed):
            buf = ((ctypes.c_ubyte * len(data))(*data) if data
                   else ctypes.POINTER(ctypes.c_ubyte)())
            return int(fn(_seed, buf, len(data)))
    elif shape == "seeded_trailing":
        len_ct = _ctype(sig.params[1][1]) or ctypes.c_size_t
        seed_ct = _ctype(sig.params[2][1]) or ctypes.c_uint
        argtypes = (ctypes.POINTER(ctypes.c_ubyte), len_ct, seed_ct)

        def adapter(fn, data: bytes, _seed=seed):
            buf = ((ctypes.c_ubyte * len(data))(*data) if data
                   else ctypes.POINTER(ctypes.c_ubyte)())
            return int(fn(buf, len(data), _seed))
    else:
        len_ct = _ctype(sig.params[1][1]) or ctypes.c_size_t
        argtypes = (ctypes.POINTER(ctypes.c_ubyte), len_ct)

        def adapter(fn, data: bytes):
            buf = ((ctypes.c_ubyte * len(data))(*data) if data
                   else ctypes.POINTER(ctypes.c_ubyte)())
            return int(fn(buf, len(data)))

    return CFunctionBinding(
        c_name=sig.name, restype=restype, argtypes=argtypes, adapter=adapter,
    )


# Fold-edge lengths worth probing for any bytewise checksum, plus the
# Adler NMAX block edges when the family matches.
_GENERIC_BOUNDARIES = [0, 1, 2, 255, 256, 257, 4096, 65536]
_ADLER_BOUNDARIES = [0, 1, 2, 5551, 5552, 5553, 11103, 11104, 11105, 65536]


# Top-level C function definition: `<ret> <name>(<params>) {` starting at column 0.
# Anchoring at line start skips indented body statements (return/if/for...), which is
# what a header prototype parser cannot do on a .c file.
_C_DEF_RE = re.compile(
    r"^(?P<ret>(?:[A-Za-z_]\w*[\s\*]+)+?)(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^;{}]*)\)\s*\{",
    re.MULTILINE,
)
_C_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "do", "else"}

# C storage-class / qualifier / calling-convention keywords that can prefix a
# return type but are not part of it.
_RET_QUAL_KEYWORDS = {
    "static", "inline", "extern", "register", "auto", "_Noreturn",
    "__inline", "__inline__", "__forceinline", "__attribute__",
    "__cdecl", "__stdcall", "__fastcall", "__declspec",
}


def _strip_return_qualifiers(ret: str) -> str:
    """Drop leading qualifier keywords AND all-caps macro tokens from a C return
    type. Real APIs prefix return types with export/inline macros — zlib's
    `ZEXPORT`, murmur3's `FORCE_INLINE`, Lua's `LUAI_FUNC`, `ZLIB_INTERNAL`.
    These are conventionally ALL_CAPS identifiers (or known keywords); the actual
    type tokens (uint32_t/size_t/void/struct names) are not. Strip leading
    junk while keeping at least the final type token(s). No hardcoded macro
    names — the all-caps convention generalizes to any codebase."""
    toks = ret.replace("*", " * ").split()
    i = 0
    while i < len(toks) - 1:  # always keep the last token as the type
        t = toks[i]
        is_kw = t in _RET_QUAL_KEYWORDS
        # ALL-CAPS identifier (len>1, letters/digits/_) that isn't a pure number
        core = t.replace("_", "")
        is_macro = (len(t) > 1 and t.isupper() and core.isalnum()
                    and not core.isdigit())
        if is_kw or is_macro:
            i += 1
            continue
        break
    return " ".join(toks[i:]).replace(" *", "*").strip() or ret


def _parse_c_definitions(c_text: str):
    from alchemist.verifier.auto_ffi import _strip_comments, _parse_params
    text = _strip_comments(c_text)
    out = []
    for m in _C_DEF_RE.finditer(text):
        name = m.group("name")
        if name in _C_KEYWORDS:
            continue
        ret = _strip_return_qualifiers(m.group("ret").strip())
        params = _parse_params(m.group("params").strip())
        out.append(CSignature(name=name, return_type=ret, params=params))
    return out


def collect_subject_signatures(c_source_dir: Path) -> list[CSignature]:
    from alchemist.verifier.build_c_dll import discover_c_build, _NONLIB_DIRS
    from alchemist.extractor.constants_extractor import (
        build_typedef_map, resolve_scalar_alias,
    )
    sigs: list[CSignature] = []
    seen: set[str] = set()
    src = Path(c_source_dir)
    _texts: list[str] = []
    for header in sorted(src.rglob("*.h")):
        if {p.lower() for p in header.relative_to(src).parts[:-1]} & _NONLIB_DIRS:
            continue
        _txt = header.read_text(encoding="utf-8", errors="replace")
        _texts.append(_txt)
        for sig in parse_header(_txt):
            if sig.name not in seen:
                seen.add(sig.name)
                sigs.append(sig)
    # Headerless single-file subjects (arbitrary cold C): parse top-level function
    # DEFINITIONS from library .c files (recursively; test/example/main drivers excluded).
    c_files, _ = discover_c_build(src)
    for cfile in c_files:
        _txt = cfile.read_text(encoding="utf-8", errors="replace")
        _texts.append(_txt)
        for sig in _parse_c_definitions(_txt):
            if sig.name not in seen:
                seen.add(sig.name)
                sigs.append(sig)
    # Resolve the subject's OWN scalar typedef aliases (lua_Integer/Instruction/
    # uInt/...) to base C primitives so the shape classifiers recognize them.
    # Read from the subject's typedefs — no hardcoded per-library type table.
    tmap = build_typedef_map(_texts)
    if tmap:
        for sig in sigs:
            sig.return_type = resolve_scalar_alias(sig.return_type or "", tmap)
            sig.params = [(n, resolve_scalar_alias(t, tmap)) for n, t in sig.params]
    return sigs


def make_checksum_bindings(
    signatures: list[CSignature],
    algs: list,
) -> dict[str, CFunctionBinding]:
    """ctypes bindings for every checksum/hash algorithm whose C export
    matches a recognized shape (scalar checksum or byte-digest hash).
    Keyed by algorithm (== C) name."""
    by_name = {s.name: s for s in signatures}
    out: dict[str, CFunctionBinding] = {}
    for alg in algs:
        if (alg.category or "") in ("cipher", "compression", "decompression"):
            continue
        sig = by_name.get(alg.name)
        if sig is None:
            continue
        shape = classify_checksum_shape(sig)
        if shape is not None:
            out[alg.name] = _binding_for(sig, shape, default_seed(alg.name))
            continue
        digest = classify_digest_shape(sig)
        if digest is not None:
            out[alg.name] = _digest_binding(sig, digest)
    return out


def fuzz_digest_vectors(dll, alg, sig, *, count: int = 20):
    """Mint fill-loop vectors for a byte-digest hash: {in, [k,] outlen} ->
    Ok(vec![digest]). Inputs are rendered against the spec's parameter names
    so the emitted test calls the generated fn with the right arity.
    """
    from alchemist.extractor.fuzz_vectors import (
        _bytes_to_rust_literal, _gen_byte_inputs, _rng, _FUZZ_SEED,
    )
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    desc = classify_digest_shape(sig)
    if desc is None:
        return []
    binding = _digest_binding(sig, desc)
    fn = binding.load(dll)
    key = canonical_key(desc.key_len) if desc.key_idx is not None else b""
    # Map spec parameters to roles by their Rust type.
    slice_params = [p for p in (alg.inputs or [])
                    if "[u8]" in (p.rust_type or "") or "Vec<u8>" in (p.rust_type or "")]
    len_params = [p for p in (alg.inputs or [])
                  if p not in slice_params and "usize" in (p.rust_type or "")]
    if not slice_params:
        return []
    msg_param = slice_params[0].name
    key_param = slice_params[1].name if len(slice_params) > 1 and desc.key_idx is not None else None
    outlen_param = len_params[0].name if len_params else None

    rng = _rng(_FUZZ_SEED)
    inputs = _gen_byte_inputs(rng, count)
    vectors = []
    for data in inputs:
        try:
            digest = binding.adapter(fn, data)
        except Exception:  # noqa: BLE001
            continue
        row = {msg_param: _bytes_to_rust_literal(bytes(data))}
        if key_param:
            row[key_param] = _bytes_to_rust_literal(bytes(key))
        if outlen_param:
            row[outlen_param] = f"{desc.digest_len}usize"
        digest_lit = "vec![" + ", ".join(f"0x{b:02x}" for b in digest) + "]"
        # Match the generated fn's return shape: a normalized digest fn returns a bare
        # `Vec<u8>` (see normalize_digest_specs); a Result-returning one needs `Ok(...)`.
        # Emitting `Ok(...)` against a bare-Vec return is a hard type-mismatch compile error
        # that no model fill can ever satisfy.
        _ret = (getattr(alg, "return_type", "") or "")
        expected = f"Ok({digest_lit})" if _ret.strip().startswith("Result<") else digest_lit
        vectors.append(SpecTestVector(
            description=f"fuzz_input_len_{len(data)}",
            source=f"C reference (digest): {sig.name}",
            inputs=row,
            expected_output=expected,
            tolerance="exact",
        ))
    return vectors


def fuzz_digest_catalog_vectors(dll, alg, sig):
    """Return the standards-catalog KATs (NIST CAVP / FIPS) for a digest fn — but ONLY after
    VALIDATING each against the subject's OWN compiled-C oracle: run the C on the KAT input and
    require its digest == the KAT's expected. This is the safe canonical-vs-variant gate:
      * a genuine SHA-256's C reproduces the FIPS-180 KATs  -> emit them, so the Rust must match
        the STANDARD (not merely == this C) — the second, independent proof for Phase 2.5;
      * a VARIANT's C won't reproduce them -> emit NONE (never assert a canonical KAT on a
        variant, the exact false-refusal the auto-oracle path guards against).
    If ANY KAT disagrees with the oracle the whole set is dropped (fail-safe)."""
    from alchemist.extractor.fuzz_vectors import _bytes_to_rust_literal
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    from alchemist.standards import lookup_test_vectors
    desc = classify_digest_shape(sig)
    if desc is None:
        return []
    try:
        kats = lookup_test_vectors(alg.name)
    except Exception:  # noqa: BLE001
        return []
    kats = [k for k in kats if k.input_hex is not None and k.expected_hex]
    if not kats:
        return []
    binding = _digest_binding(sig, desc)
    fn = binding.load(dll)
    slice_params = [p for p in (alg.inputs or [])
                    if "[u8]" in (p.rust_type or "") or "Vec<u8>" in (p.rust_type or "")]
    if not slice_params:
        return []
    msg_param = slice_params[0].name
    _ret = (getattr(alg, "return_type", "") or "").strip()
    out = []
    for kat in kats:
        exp = kat.expected_bytes
        if len(exp) != desc.digest_len:
            return []  # catalog width != this fn's digest width -> not our algorithm
        try:
            got = bytes(binding.adapter(fn, kat.input_bytes))
        except Exception:  # noqa: BLE001
            return []
        if got != exp:
            return []  # compiled C does NOT match the standard KAT -> not canonical -> emit none
        digest_lit = "vec![" + ", ".join(f"0x{b:02x}" for b in exp) + "]"
        expected = f"Ok({digest_lit})" if _ret.startswith("Result<") else digest_lit
        out.append(SpecTestVector(
            description=f"CAVP_{kat.name}",
            source=f"NIST/FIPS catalog (oracle-validated canonical): {alg.name} {kat.name}",
            inputs={msg_param: _bytes_to_rust_literal(kat.input_bytes)},
            expected_output=expected,
            tolerance="exact",
        ))
    return out


def classify_scalar_shape(sig) -> str | None:
    """All-scalar signature: every param is an int/char scalar and the return is a scalar.
    e.g. isqrt(unsigned)->unsigned, popcount(unsigned long)->int,
    update_crc_32(uint32_t, unsigned char)->uint32_t. -> 'scalar' | None.
    Works for any arity >= 1; adapter/proptest/oracle handle N by-value scalar args."""
    if not _ctype(sig.return_type or ""):
        return None
    params = [t.strip() for _, t in sig.params]
    if not params:
        return None
    if all(_SCALAR_ARG.match(p) for p in params):
        return "scalar"
    return None


def _scalar_binding(sig):
    argtypes = tuple(_ctype(t) or ctypes.c_long for _, t in sig.params)
    restype = _ctype(sig.return_type) or ctypes.c_long

    def adapter(fn, values):
        return int(fn(*values))

    return CFunctionBinding(c_name=sig.name, restype=restype, argtypes=argtypes, adapter=adapter)


def fuzz_scalar_vectors(dll, alg, sig, *, count: int = 40):
    """Mint fill-loop vectors for an all-scalar function from the compiled C oracle.
    Values are kept in [0, 2**31) so they compile as positive literals for any int
    width; the proptest differential (verify) fuzzes the full type range."""
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    if classify_scalar_shape(sig) is None:
        return []
    inputs_specs = alg.inputs or []
    if len(inputs_specs) != len(sig.params):
        return []
    binding = _scalar_binding(sig)
    fn = binding.load(dll)

    import os as _os
    _safe_scalar = bool(_os.environ.get("ALCHEMIST_SAFE_SCALAR"))

    def _range(rust_type):
        rt = (rust_type or "u64").strip()
        signed = rt.startswith("i")
        w = 64
        mm = re.search(r"(8|16|32|64|128)", rt)
        if mm and mm.group(1) != "128":
            w = int(mm.group(1))
        lo = -(1 << (w - 1)) if signed else 0
        hi = (1 << (w - 1)) - 1 if signed else (1 << w) - 1
        if _safe_scalar:
            # Contract-domain functions (glibc ctype: isdigit/tolower index
            # __ctype_b_loc()[c] and SEGFAULT outside [-1,255]; codepoint/char
            # helpers) are UB out of domain. When flagged, restrict int inputs
            # to the safe char domain [-1,255] so the oracle produces valid
            # vectors instead of crashing. Verification is then honest over that
            # tested domain (byte-exact on chars), not the full type width.
            lo = max(lo, -1)
            hi = min(hi, 255)
        return lo, hi, w

    # per-param value pools: boundaries + spread across the FULL width so the fill
    # loop catches edge bugs (overflow, high bits) rather than letting them reach verify.
    pools = []
    for p_spec in inputs_specs:
        lo, hi, _w = _range(p_spec.rust_type)
        pool = [0, 1, 2, 3, hi, hi - 1, hi // 2, hi // 3]
        if lo < 0:
            pool += [lo, lo + 1, -1, -2]
        pool = [v for v in dict.fromkeys(pool) if lo <= v <= hi]
        st = 0xD1B54A32D192ED03 ^ (hash(p_spec.name) & 0xFFFF)
        while len(pool) < count:
            st = (st * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
            pool.append(lo + ((st >> 3) % (hi - lo + 1)))
        pools.append(pool[:count])

    vectors, seen = [], set()
    for i in range(count):
        vals = tuple(pool[i] for pool in pools) if pools else ()
        if vals in seen:
            continue
        seen.add(vals)
        try:
            out = binding.adapter(fn, vals)
        except Exception:  # noqa: BLE001
            continue
        row = {}
        for p_spec, v in zip(inputs_specs, vals):
            rt = (p_spec.rust_type or "u64").strip()
            row[p_spec.name] = f"{v}{rt}"
        vectors.append(SpecTestVector(
            description=f"scalar_{i}",
            source=f"C reference (scalar): {sig.name}",
            inputs=row,
            expected_output=str(int(out)),
            tolerance="exact",
        ))
    return vectors


_MUT_BYTE_PTR_LOOSE = re.compile(r"^(char|unsigned char|uint8_t|u_char|Bytef)\s*\*$")


def classify_inplace_shape(sig) -> str | None:
    """void fn(mutable byte-buffer, len) -> in-place byte transform (str_reverse)."""
    if (sig.return_type or "").strip() not in ("void", ""):
        return None
    params = [t.strip() for _, t in sig.params]
    if (len(params) == 2 and _MUT_BYTE_PTR_LOOSE.match(params[0])
            and _INT_C_TYPES.match(params[1])):
        return "inplace"
    return None


def fuzz_inplace_vectors(dll, alg, sig, *, count: int = 24):
    """Mint fill-loop vectors for an in-place byte transform: run the C on a buffer,
    capture the buffer AFTER mutation. Emits byte_transform vectors the test-generator
    already understands (buffer_postcondition)."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import (
        _bytes_to_rust_literal, _gen_byte_inputs, _rng, _FUZZ_SEED,
    )
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    if classify_inplace_shape(sig) is None:
        return []
    inputs_specs = alg.inputs or []
    buf_param = next((p for p in inputs_specs if "[u8]" in (p.rust_type or "")), None)
    len_param = next((p for p in inputs_specs
                      if p is not buf_param and "usize" in (p.rust_type or "")), None)
    if buf_param is None or len_param is None:
        return []
    fn = getattr(dll, sig.name)
    fn.restype = None
    fn.argtypes = (ctypes.POINTER(ctypes.c_ubyte), _ctype(sig.params[1][1]) or ctypes.c_int)
    rng = _rng(_FUZZ_SEED)
    vectors = []
    for data in _gen_byte_inputs(rng, count):
        data = bytes(data)
        buf = (ctypes.c_ubyte * len(data))(*data) if data else (ctypes.c_ubyte * 0)()
        try:
            fn(buf, len(data))
        except Exception:  # noqa: BLE001
            continue
        after = bytes(buf[i] for i in range(len(data)))
        vec_lit = "__VEC__" + ",".join(str(b) for b in data)
        vectors.append(SpecTestVector(
            description=f"inplace_len_{len(data)}",
            source=f"C reference (in-place): {sig.name}",
            inputs={buf_param.name: vec_lit, len_param.name: f"{len(data)}usize"},
            expected_output=_bytes_to_rust_literal(after),
            tolerance=f"byte_transform|buffer_postcondition|{buf_param.name}|{len_param.name}",
        ))
    return vectors


def classify_buf_transform(sig) -> str | None:
    """`<int> f(<byteptr> in, <int> inlen, <byteptr> out, <int> outlen)` that RETURNS the number
    of bytes written to `out`: a variable-length buffer transform — a codec (compress / encode /
    decode). Verified byte-exact by comparing `out[0..ret]` and `ret`, C vs Rust, over fuzzed
    inputs; the extractor lifts it to `fn(input: &[u8]) -> Vec<u8>` (the returned Vec IS the
    written output). Distinct from the digest shape (whose output length is FIXED). This is the
    Phase-3 shape that lets a real codec — where `goto` usually lives — be verified at all."""
    if (sig.return_type or "").strip() not in (
            "int", "size_t", "long", "ssize_t", "unsigned", "unsigned int", "uint32_t"):
        return None
    p = [t.strip() for _, t in sig.params]
    if (len(p) == 4 and _BYTE_PTR.match(p[0]) and _INT_C_TYPES.match(p[1])
            and _BYTE_PTR.match(p[2]) and _INT_C_TYPES.match(p[3])):
        return "buf_transform"
    return None


# Decoder -> its paired encoder. A DECODER fuzzed with random bytes is a trap:
# random input is almost never a valid encoded stream, so the C decoder walks
# off the end of a truncated frame (undefined behavior — reads past the buffer),
# while a memory-safe Rust translation bounds-checks and stops. They then
# diverge on inputs no correct translation could ever match. The fix is to feed
# the decoder VALID streams minted by running its encoder first (round-trip
# fuzzing), so C never takes a UB path and byte-exact agreement is achievable.
_DECODER_ENCODER_PAIRS = (
    ("decompress", "compress"),
    ("uncompress", "compress"),
    ("decode", "encode"),
    ("inflate", "deflate"),
    ("unpack", "pack"),
    ("expand", "compress"),
)


def _paired_encoder_name(decoder_name: str) -> "str | None":
    """If `decoder_name` looks like a decoder, return the name of its likely
    encoder (same casing/prefix, verb swapped). e.g. smaz_decompress ->
    smaz_compress, tinf_uncompress -> tinf_compress. None if not a decoder."""
    lo = decoder_name.lower()
    for dec, enc in _DECODER_ENCODER_PAIRS:
        idx = lo.rfind(dec)
        if idx != -1:
            return decoder_name[:idx] + enc + decoder_name[idx + len(dec):]
    return None


def fuzz_buf_transform_vectors(dll, alg, sig, *, count: int = 24):
    """Mint fill-loop vectors for a variable-length buffer transform: run the compiled C on a
    fuzzed input buffer, capture `out[0..return_value]`. Emits `&[u8] -> Vec<u8>` vectors the
    generic (exact) test-emitter already understands.

    For DECODERS (decompress/decode/inflate/...), inputs are minted by running
    the paired ENCODER on random plaintext (round-trip fuzzing) so the decoder
    only ever sees valid streams — otherwise the C decoder's undefined behavior
    on malformed input makes byte-exact verification impossible."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import (
        _bytes_to_rust_literal, _gen_byte_inputs, _rng, _FUZZ_SEED,
    )
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    if classify_buf_transform(sig) is None:
        return []
    slice_params = [p for p in (alg.inputs or []) if "[u8]" in (p.rust_type or "")]
    if not slice_params:
        return []
    msg_param = slice_params[0].name
    fn = getattr(dll, sig.name)
    fn.restype = ctypes.c_int
    _lenct = _ctype(sig.params[1][1]) or ctypes.c_int
    fn.argtypes = (ctypes.POINTER(ctypes.c_ubyte), _lenct,
                   ctypes.POINTER(ctypes.c_ubyte), _lenct)
    # Round-trip fuzzing for decoders: bind the paired encoder if the subject
    # exports one, so we can mint valid streams instead of random garbage.
    encoder = None
    _enc_name = _paired_encoder_name(sig.name)
    if _enc_name and hasattr(dll, _enc_name):
        encoder = getattr(dll, _enc_name)
        encoder.restype = ctypes.c_int
        encoder.argtypes = fn.argtypes
    rng = _rng(_FUZZ_SEED)
    _ret = (getattr(alg, "return_type", "") or "").strip()
    vectors = []
    for data in _gen_byte_inputs(rng, count):
        data = bytes(data)
        if encoder is not None:
            # `data` is random plaintext; encode it to a valid stream for the decoder.
            _pbuf = (ctypes.c_ubyte * len(data))(*data) if data else (ctypes.c_ubyte * 1)()
            _ecap = len(data) * 4 + 512
            _ebuf = (ctypes.c_ubyte * _ecap)()
            try:
                _er = int(encoder(_pbuf, len(data), _ebuf, _ecap))
            except Exception:  # noqa: BLE001
                continue
            if _er < 0 or _er > _ecap:
                continue
            data = bytes(_ebuf[i] for i in range(_er))
        inbuf = (ctypes.c_ubyte * len(data))(*data) if data else (ctypes.c_ubyte * 1)()
        cap = len(data) * 4 + 512
        out = (ctypes.c_ubyte * cap)()
        try:
            ret = int(fn(inbuf, len(data), out, cap))
        except Exception:  # noqa: BLE001
            continue
        if ret < 0 or ret > cap:
            continue  # overflow/error sentinel — can't represent as a clean output Vec
        result = bytes(out[i] for i in range(ret))
        lit = "vec![" + ", ".join(f"0x{b:02x}" for b in result) + "]"
        vectors.append(SpecTestVector(
            description=f"transform_len_{len(data)}",
            source=f"C reference (buf_transform): {sig.name}",
            inputs={msg_param: _bytes_to_rust_literal(data)},
            expected_output=(f"Ok({lit})" if _ret.startswith("Result<") else lit),
            tolerance="exact",
        ))
    return vectors


def classify_cbuf_out(sig) -> str | None:
    """C `<byteptr> f(const <byteptr> in, <byteptr> out)` — reads a NUL/delimiter-terminated
    input string and writes a result STRING into a caller-provided output buffer, returning
    the buffer. The extractor lifts it to `fn(input: &str) -> String`. (NMEA checksum:
    `checksum_NMEA(const unsigned char *input_str, unsigned char *result) -> unsigned char*`.)"""
    if not _BYTE_PTR.match((sig.return_type or "").strip()):
        return None
    params = [t.strip() for _, t in sig.params]
    if (len(params) == 2 and _BYTE_PTR.match(params[0])
            and params[0].startswith("const") and _MUT_BYTE_PTR_LOOSE.match(params[1])):
        return "cbuf_out"
    return None


def _rust_str_lit(s: str) -> str:
    """A Rust `&str` literal for an ASCII string. Escapes backslash, quote and control
    characters (CR/LF/TAB and other non-printables) — a bare CR/LF in a Rust string literal
    is a compile error, and the NMEA fuzzer deliberately emits '\\r'/'\\n' terminators."""
    out = []
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append(f"\\x{o:02x}")
    return '"' + "".join(out) + '"'


def fuzz_cbuf_out_vectors(dll, alg, sig, *, count: int = 24):
    """Mint fill-loop vectors for a cbuf_out fn: run the compiled C on a fuzzed input string,
    read the result STRING back out of the caller buffer. Emits `&str -> String` vectors with
    a `str_exact` tolerance the test-generator compares with assert_eq!."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    if classify_cbuf_out(sig) is None:
        return []
    str_param = next((p for p in (alg.inputs or [])
                      if "str" in (p.rust_type or "").lower() or "[u8]" in (p.rust_type or "")),
                     None)
    if str_param is None:
        return []
    fn = getattr(dll, sig.name)
    fn.restype = ctypes.c_void_p
    fn.argtypes = (ctypes.c_char_p, ctypes.POINTER(ctypes.c_ubyte))
    rng = _rng(_FUZZ_SEED)
    # NMEA-ish inputs: printable ASCII incl. the '$' start marker and '*'/CR/LF terminators
    # the algorithm keys off, so the fuzz exercises the delimiter handling.
    alphabet = [ord(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,.-$*"] + [13, 10]
    seen: set[bytes] = set()
    vectors = []
    tries = 0
    while len(vectors) < count and tries < count * 12:
        tries += 1
        n = rng.randint(0, 24)
        s = bytes(alphabet[rng.randint(0, len(alphabet) - 1)] for _ in range(n))
        if b"\x00" in s or s in seen:
            continue
        seen.add(s)
        out = (ctypes.c_ubyte * 16)()
        try:
            fn(s, out)
        except Exception:  # noqa: BLE001
            continue
        ob = bytes(out[i] for i in range(16))
        res = ob.split(b"\x00", 1)[0].decode("ascii", "replace")
        inp = s.decode("ascii", "replace")
        vectors.append(SpecTestVector(
            description=f"nmea_len_{n}",
            source=f"C reference (cbuf_out): {sig.name}",
            inputs={str_param.name: _rust_str_lit(inp)},
            expected_output=_rust_str_lit(res),
            tolerance="str_exact",
        ))
    return vectors


def classify_cstr_out(sig) -> str | None:
    """C `char* f(char*)` — a single NUL-terminated string in, returns a heap-allocated
    NUL-terminated string (caller frees). Text transforms / encoders: base64_encode,
    to_upper, url_encode. The extractor lifts it to `fn(&[u8]|&str) -> String`.

    Only the TEXT-out case is oracle-able through the C `char*` return; a binary-out lift
    (decoders → `Vec<u8>`/`Result`) can't be compared this way because the C string is
    truncated at the first NUL — the fuzzer declines those (returns []) so they refuse
    honestly rather than verify against a lossy oracle."""
    if _CHAR_PTR.match((sig.return_type or "").strip()) is None:
        return None
    params = [t.strip() for _, t in sig.params]
    if len(params) == 1 and _CHAR_PTR.match(params[0]):
        return "cstr_out"
    return None


def _rust_bytes_lit(b: bytes) -> str:
    """A Rust byte-string literal `b"..."` for arbitrary bytes (used when the extractor
    lifted a `char*` input to `&[u8]` rather than `&str`)."""
    out = []
    for o in b:
        ch = chr(o)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append(f"\\x{o:02x}")
    return 'b"' + "".join(out) + '"'


def fuzz_cstr_out_vectors(dll, alg, sig, *, count: int = 24):
    """Mint fill-loop vectors for a cstr_out fn: run the compiled C on a fuzzed printable
    input string, read the returned `char*` as a NUL-terminated string. Emits
    `(&[u8]|&str) -> String` vectors with `str_exact` tolerance. Declines any function
    whose Rust return isn't a plain `String` (binary-out lifts are NUL-lossy here)."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    if classify_cstr_out(sig) is None:
        return []
    # Oracle-able only when the Rust side returns a plain String (text out).
    ret = (alg.return_type or "").strip()
    if "String" not in ret or "Result" in ret or "Vec" in ret:
        return []
    in_param = next(
        (p for p in (alg.inputs or [])
         if "[u8]" in (p.rust_type or "") or "str" in (p.rust_type or "").lower()),
        None,
    )
    if in_param is None:
        return []
    is_bytes = "[u8]" in (in_param.rust_type or "")
    fn = getattr(dll, sig.name)
    fn.restype = ctypes.c_char_p
    fn.argtypes = (ctypes.c_char_p,)
    rng = _rng(_FUZZ_SEED)
    # Printable ASCII only (no NUL, no control chars) so both sides see identical input and
    # the C `char*` result reads back losslessly.
    alphabet = [ord(c) for c in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,-_+/"]
    seen: set[bytes] = set()
    vectors = []
    tries = 0
    while len(vectors) < count and tries < count * 12:
        tries += 1
        n = rng.randint(0, 24)
        s = bytes(alphabet[rng.randint(0, len(alphabet) - 1)] for _ in range(n))
        if s in seen:
            continue
        seen.add(s)
        try:
            res = fn(s)  # c_char_p restype → bytes up to NUL (or None)
        except Exception:  # noqa: BLE001
            continue
        res_s = res.decode("ascii", "replace") if isinstance(res, (bytes, bytearray)) else ""
        inp = s.decode("ascii", "replace")
        in_lit = _rust_bytes_lit(s) if is_bytes else _rust_str_lit(inp)
        vectors.append(SpecTestVector(
            description=f"cstr_len_{n}",
            source=f"C reference (cstr_out): {sig.name}",
            inputs={in_param.name: in_lit},
            expected_output=_rust_str_lit(res_s),
            tolerance="str_exact",
        ))
    return vectors


def classify_cstr_roundtrip(sig, by_name) -> "str | None":
    """A `char* f(char*)` DECODER paired with an oracle-able ENCODER in the
    same subject. base64_decode / *_decode / *_uncompress etc. lift to
    `Result<Vec<u8>, E>` (binary out) or `String`, which `cstr_out` correctly
    DECLINES because the C `char*` return is NUL-lossy for binary and random
    fuzz strings are not valid encoded streams — so the decoder refuses with
    "no verifiable test vectors".

    The fix is a ROUNDTRIP oracle: mint valid inputs by running the compiled C
    encoder on random plaintext `p`, then require `decode(encode(p)) == p`. The
    encoder is the C reference, so this is a sound differential. Returns the
    paired ENCODER's name (which must itself be the `char* enc(char*)` cstr_out
    shape and present in the subject), or None.

    Checked BEFORE cstr_out in both the vector-synth and harness dispatch: the
    two share the `char* f(char*)` signature, and only a *named decoder with a
    real encoder partner* takes this branch (encoders never match
    `_paired_encoder_name`), so text encoders still flow to cstr_out."""
    if _CHAR_PTR.match((sig.return_type or "").strip()) is None:
        return None
    params = [t.strip() for _, t in sig.params]
    if not (len(params) == 1 and _CHAR_PTR.match(params[0])):
        return None
    enc = _paired_encoder_name(sig.name)
    if not enc or enc not in by_name:
        return None
    if classify_cstr_out(by_name[enc]) is None:
        return None
    return enc


def fuzz_cstr_roundtrip_vectors(dll, alg, sig, enc_name, *, count: int = 24):
    """Mint decoder fill-loop vectors by running the compiled C ENCODER on random
    plaintext: `p` (non-NUL bytes) -> C encode -> valid encoded string `ct`; emit
    `(&str) -> <bytes|text>` vectors whose expected output is `p` itself. The
    roundtrip identity `decode(encode(p)) == p` IS the oracle (the encoder is the
    compiled C reference). tolerance="roundtrip" routes to `_emit_roundtrip_test`."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    if _paired_encoder_name(sig.name) != enc_name:
        return []
    enc = getattr(dll, enc_name, None)
    if enc is None:
        return []
    enc.restype = ctypes.c_char_p
    enc.argtypes = (ctypes.c_char_p,)
    ret = (alg.return_type or "").strip()
    text_out = ("String" in ret) and ("Vec" not in ret)
    in_param = next((p for p in (alg.inputs or [])
                     if "str" in (p.rust_type or "").lower()
                     or "[u8]" in (p.rust_type or "")), None)
    if in_param is None:
        return []
    in_is_str = "str" in (in_param.rust_type or "").lower()
    rng = _rng(_FUZZ_SEED)
    # Plaintext: non-NUL bytes (the C encoder takes a NUL-terminated char*). A
    # text-out decoder additionally needs printable plaintext so it reads back
    # as a String losslessly.
    if text_out:
        alphabet = [ord(c) for c in
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,-_+/"]
    else:
        # ASCII, non-NUL. High bytes (>=128) are deliberately excluded: a C
        # encoder that indexes a lookup table by a SIGNED `char` (base64's
        # `buffer[0] >> 2`) has undefined behavior on them and emits garbage —
        # a memory-safe Rust decoder cannot (and must not) reproduce that, so
        # minting from those inputs would forge an unsatisfiable vector. ASCII
        # plaintext keeps every reasonable char-based codec in its defined
        # domain while still exercising the full decode alphabet.
        alphabet = list(range(1, 128))
    seen: set[bytes] = set()
    vectors = []
    tries = 0
    while len(vectors) < count and tries < count * 12:
        tries += 1
        n = rng.randint(0, 24)
        p = bytes(alphabet[rng.randint(0, len(alphabet) - 1)] for _ in range(n))
        if p in seen:
            continue
        seen.add(p)
        try:
            ct = enc(p)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(ct, (bytes, bytearray)):
            continue
        ct_bytes = bytes(ct)
        # Encoder failure (NULL / empty output for a non-empty plaintext) would
        # mint a bogus `decode("") == p` vector — drop it. An empty plaintext
        # legitimately encodes to empty, so only guard the non-empty case.
        if len(p) > 0 and len(ct_bytes) == 0:
            continue
        # A `&str`-input decoder needs the encoded stream to be valid ASCII (a
        # real caller passes text). Standard base64 output is always ASCII; a
        # non-ASCII byte means the encoder misbehaved on this input — skip it
        # (also, a non-ASCII byte cannot be rendered in a Rust `"..."` literal).
        if in_is_str and any(b >= 128 for b in ct_bytes):
            continue
        ct_s = ct_bytes.decode("ascii", "replace")
        in_lit = _rust_str_lit(ct_s) if in_is_str else _rust_bytes_lit(bytes(ct))
        expected = (_rust_str_lit(p.decode("ascii", "replace"))
                    if text_out else _rust_bytes_lit(p))
        vectors.append(SpecTestVector(
            description=f"roundtrip_ptlen_{n}",
            source=f"C reference (roundtrip via {enc_name}): {sig.name}",
            inputs={in_param.name: in_lit},
            expected_output=expected,
            tolerance="roundtrip",
        ))
    return vectors


# A pointer to an array of a NON-byte integer scalar (int/long/short/...). The
# checksum/digest shapes own single-byte element pointers (char/uint8_t), so this
# deliberately excludes them to avoid stealing byte-buffer checksums.
_INT_ARRAY_PTR = re.compile(
    r"^(const\s+)?(unsigned\s+long\s+long|long\s+long|unsigned\s+long|unsigned\s+short|"
    r"unsigned\s+int|unsigned|int|long|short|"
    r"uint16_t|uint32_t|uint64_t|int16_t|int32_t|int64_t)\s*\*$")


def classify_iarray_reduce(sig):
    """C `<scalar> f(const T* a, <int> n)` — a pointer to an array of a non-byte
    integer scalar T plus a length, reducing to a scalar (sum/min/max/dot/count).
    Byte-element pointers stay with the checksum/digest shapes; this covers
    int/long/short arrays. The extractor lifts it to `fn(a: &[T]) -> R`.

    Returns {elem_c, elem_rust, ret_rust} or None."""
    ret = (sig.return_type or "").strip()
    if _ctype(ret) is None:
        return None
    params = [t.strip() for _, t in sig.params]
    if len(params) != 2:
        return None
    m = _INT_ARRAY_PTR.match(params[0])
    if m is None:
        return None
    if _INT_C_TYPES.match(params[1]) is None and _SIZE_T.match(params[1]) is None:
        return None
    from alchemist.verifier import struct_lift
    elem_c = m.group(2)
    return {
        "elem_c": elem_c,
        "elem_rust": struct_lift.c_scalar_to_rust(elem_c) or "i32",
        "ret_rust": struct_lift.c_scalar_to_rust(ret) or "i64",
    }


def _elem_range(elem_rust: str, cap: int = 1 << 20):
    """(lo, hi) for a scalar element, clamped to +-cap so a reduction (sum) over a
    bounded-length array cannot overflow the C reference into signed-overflow UB —
    which would make the oracle undefined. Verification is honest over this domain."""
    signed = elem_rust.startswith("i")
    mm = re.search(r"(8|16|32|64)", elem_rust)
    w = int(mm.group(1)) if mm else 32
    lo = -(1 << (w - 1)) if signed else 0
    hi = (1 << (w - 1)) - 1 if signed else (1 << w) - 1
    return max(lo, -cap), min(hi, cap)


def fuzz_iarray_reduce_vectors(dll, alg, sig, *, count: int = 24):
    """Mint fill-loop vectors for an int-array reduction: build a random array of the
    element type, run the compiled C over (ptr, len), compare the scalar result.
    Emits `&[T] -> R` vectors with `exact` tolerance."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    desc = classify_iarray_reduce(sig)
    if desc is None:
        return []
    slice_param = next((p for p in (alg.inputs or []) if "[" in (p.rust_type or "")), None)
    if slice_param is None:
        return []
    elem_ct = _ctype(desc["elem_c"]) or ctypes.c_int
    fn = getattr(dll, sig.name)
    fn.restype = _ctype(sig.return_type) or ctypes.c_long
    fn.argtypes = (ctypes.POINTER(elem_ct), ctypes.c_int)
    rng = _rng(_FUZZ_SEED)
    elem_rust = desc["elem_rust"]
    lo, hi = _elem_range(elem_rust)
    vectors = []
    for i in range(count):
        n = rng.randint(0, 16)
        arr = [rng.randint(lo, hi) for _ in range(n)]
        carr = (elem_ct * n)(*arr)
        try:
            out = fn(carr, n)
        except Exception:  # noqa: BLE001
            continue
        lit = "&[" + ", ".join(f"{v}{elem_rust}" for v in arr) + "]"
        vectors.append(SpecTestVector(
            description=f"iarray_{i}_len{n}",
            source=f"C reference (iarray_reduce): {sig.name}",
            inputs={slice_param.name: lit},
            expected_output=str(int(out)),
            tolerance="exact",
        ))
    return vectors


def classify_cstr_scalar(sig):
    """C `<scalar> f(const char* s, <scalar>...)` — a NUL-terminated string plus zero
    or more by-value scalars, returning a scalar (count_char, strlen, atoi, char-index).
    The extractor lifts it to `fn(s: &str|&[u8], ...) -> R`.

    Returns the list of extra-scalar C param types (possibly empty), or None.
    A `(const char*, <int-len>)` shape is a byte BUFFER, owned by classify_checksum
    (checked first in build_diff_config); this catches the string+char / bare-string
    cases that shape misses."""
    if _ctype(sig.return_type or "") is None:
        return None
    params = [t.strip() for _, t in sig.params]
    if not params or _CHAR_PTR.match(params[0]) is None:
        return None
    extras = params[1:]
    if not all(_SCALAR_ARG.match(p) for p in extras):
        return None
    return extras


def fuzz_cstr_scalar_vectors(dll, alg, sig, *, count: int = 32):
    """Mint fill-loop vectors for a `<scalar> f(const char* s, ...scalars)` fn: fuzz a
    printable string + random scalars, run the compiled C, compare the scalar result.
    Emits vectors with `exact` tolerance."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    extras = classify_cstr_scalar(sig)
    if extras is None:
        return []
    str_param = next((p for p in (alg.inputs or [])
                      if "str" in (p.rust_type or "").lower() or "[u8]" in (p.rust_type or "")), None)
    if str_param is None:
        return []
    scalar_params = [p for p in (alg.inputs or []) if p is not str_param]
    if len(scalar_params) != len(extras):
        return []
    is_bytes = "[u8]" in (str_param.rust_type or "")
    fn = getattr(dll, sig.name)
    fn.restype = _ctype(sig.return_type) or ctypes.c_int
    fn.argtypes = tuple([ctypes.c_char_p] + [_ctype(e) or ctypes.c_int for e in extras])
    rng = _rng(_FUZZ_SEED)
    alphabet = [ord(c) for c in
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,-_"]
    vectors = []
    for i in range(count):
        n = rng.randint(0, 24)
        s = bytes(alphabet[rng.randint(0, len(alphabet) - 1)] for _ in range(n))
        svals = []
        for sp in scalar_params:
            lo, hi = _elem_range((sp.rust_type or "i32").strip(), cap=127)
            svals.append(rng.randint(lo, hi))
        try:
            out = fn(s, *svals)
        except Exception:  # noqa: BLE001
            continue
        row = {str_param.name: (_rust_bytes_lit(s) if is_bytes else _rust_str_lit(s.decode("ascii", "replace")))}
        for sp, v in zip(scalar_params, svals):
            row[sp.name] = f"{v}{(sp.rust_type or 'i32').strip()}"
        vectors.append(SpecTestVector(
            description=f"cstr_scalar_{i}_len{n}",
            source=f"C reference (cstr_scalar): {sig.name}",
            inputs=row,
            expected_output=str(int(out)),
            tolerance="exact",
        ))
    return vectors


def classify_buf_gen(sig):
    """C `<byteptr> f(<size> n, <scalar>...)` — a buffer GENERATOR: allocates and
    returns a heap byte buffer of `n` bytes computed from the scalar args
    (make_buffer's `buf[i]=fill+i`, memset/pattern/PRNG fills). Param 0 is the
    length. The extractor lifts it to `fn(n: usize, ...) -> Vec<u8>`.

    Returns the list of extra-scalar C param types (after the length), or None."""
    if _BYTE_PTR.match((sig.return_type or "").strip()) is None:
        return None
    params = [t.strip() for _, t in sig.params]
    if not params:
        return None
    if _INT_C_TYPES.match(params[0]) is None and _SIZE_T.match(params[0]) is None:
        return None
    extras = params[1:]
    if not all(_SCALAR_ARG.match(p) for p in extras):
        return None
    return extras


def fuzz_buf_gen_vectors(dll, alg, sig, *, count: int = 32):
    """Mint fill-loop vectors for a buffer generator: fuzz the length + scalar args,
    run the compiled C, read the returned `n` bytes back, compare as a byte Vec.
    Leaks the C pointer (never freeing is sound; the fuzz lengths are small)."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED, _bytes_to_rust_literal
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    extras = classify_buf_gen(sig)
    if extras is None:
        return []
    ret = (alg.return_type or "").strip()
    len_param = (alg.inputs or [None])[0]
    scalar_params = list(alg.inputs or [])[1:]
    if len_param is None or len(scalar_params) != len(extras):
        return []
    fn = getattr(dll, sig.name)
    fn.restype = ctypes.c_void_p
    fn.argtypes = tuple([_ctype(sig.params[0][1]) or ctypes.c_size_t]
                        + [_ctype(e) or ctypes.c_int for e in extras])
    rng = _rng(_FUZZ_SEED)
    vectors = []
    for i in range(count):
        n = rng.randint(0, 48)
        svals = []
        for sp in scalar_params:
            lo, hi = _elem_range((sp.rust_type or "u8").strip(), cap=255)
            svals.append(rng.randint(lo, hi))
        try:
            ptr = fn(n, *svals)
        except Exception:  # noqa: BLE001
            continue
        if not ptr and n > 0:
            continue
        buf = ctypes.string_at(ptr, n) if (ptr and n) else b""
        row = {len_param.name: f"{n}usize"}
        for sp, v in zip(scalar_params, svals):
            row[sp.name] = f"{v}{(sp.rust_type or 'u8').strip()}"
        lit = _bytes_to_rust_literal(buf)
        vectors.append(SpecTestVector(
            description=f"buf_gen_{i}_n{n}",
            source=f"C reference (buf_gen): {sig.name}",
            inputs=row,
            expected_output=(f"Ok({lit})" if ret.startswith("Result<") else lit),
            tolerance="exact",
        ))
    return vectors


def normalize_byte_buffer_types(c_source_dir, specs) -> int:
    """Force `&[u8]` for any spec input whose C type is a char*/byte pointer that comes
    with a length parameter. Such params are byte BUFFERS, not C strings; lifting them to
    `&str` makes them un-verifiable with arbitrary bytes (non-UTF-8 fails from_utf8).
    Mutates alg.inputs[*].rust_type. Returns the number of params changed."""
    try:
        sigs = {s.name: s for s in collect_subject_signatures(Path(c_source_dir))}
    except Exception:  # noqa: BLE001
        return 0
    changed = 0
    char_ptr = re.compile(r"^(const\s+)?char\s*\*$")
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            if sig is None:
                continue
            c_by_name = {n: (t or "").strip() for n, t in sig.params}
            has_len = any(_INT_C_TYPES.match((t or "").strip()) for _, t in sig.params)
            if not has_len:
                continue
            for inp in alg.inputs or []:
                ct = c_by_name.get(inp.name, "")
                if char_ptr.match(ct) and inp.rust_type != "&[u8]":
                    inp.rust_type = "&[u8]"
                    changed += 1
    return changed


_C_CHAR_SCALAR = re.compile(r"^(const\s+)?(signed\s+|unsigned\s+)?char$")


def normalize_char_scalar_params(c_source_dir, specs) -> int:
    """A C `char` VALUE arg (a byte being compared/indexed, e.g. count_char's needle)
    gets lifted by the generic lifter to Rust `char` — a 4-byte Unicode scalar that has
    no integer-literal form, can't round-trip the byte-oriented C oracle (the delimiter
    ends up mis-rendered), and casts awkwardly to the FFI byte. Re-lift such params to
    `i8`/`u8` (C `char` is signed on x86-64) so the fill + differential machinery treats
    them as the bytes they are. Only touches by-value scalars whose C type is a plain
    char; pointers (`char*` strings) are untouched. Returns the count changed."""
    try:
        sigs = {s.name: s for s in collect_subject_signatures(Path(c_source_dir))}
    except Exception:  # noqa: BLE001
        return 0
    changed = 0
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            if sig is None:
                continue
            c_params = [t.strip() for _, t in sig.params]
            for idx, inp in enumerate(alg.inputs or []):
                if (inp.rust_type or "").strip() != "char":
                    continue
                if idx < len(c_params) and _C_CHAR_SCALAR.match(c_params[idx]):
                    inp.rust_type = "u8" if "unsigned" in c_params[idx] else "i8"
                    changed += 1
    return changed


def normalize_digest_specs(c_source_dir, specs) -> int:
    """For a function the C exposes as a byte-digest (`int f(const in*, inlen, [key,] out*,
    outlen)`, SipHash/SHA family), rewrite the spec so the Rust fn RETURNS the digest:
    `fn f(data: &[u8]) -> Vec<u8>`. The generic lifter otherwise produces
    `f(&[u8], &mut [u8]) -> Result<(), E>` (out-param), which mismatches the digest differential
    adapter (it expects the digest as the return) AND, being fallible, invites the architect to
    wrap a one-shot hash in a Hasher trait + error hierarchy. Returns the count normalized."""
    try:
        sigs = {s.name: s for s in collect_subject_signatures(Path(c_source_dir))}
    except Exception:  # noqa: BLE001
        return 0
    n = 0
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            sig = sigs.get(alg.name)
            is_buf_transform = classify_buf_transform(sig) is not None if sig else False
            hash_out = classify_hash_out_shape(sig) if sig else None
            if sig is None or (classify_digest_shape(sig) is None
                               and not is_buf_transform and hash_out is None):
                continue
            # Keep the read-only byte-slice input(s) (message [+ key]); drop the out buffer
            # and any length param — the returned Vec IS the written output.
            byte_slices = [p for p in (alg.inputs or []) if "[u8]" in (p.rust_type or "")]
            if hash_out is not None:
                # Seeded hash-to-outbuf (MurmurHash): keep the message slice + the seed
                # scalar (by its C name), drop the length param and the out buffer. The
                # returned Vec is the fixed-size digest.
                seed_name = sig.params[hash_out.seed_idx][0]
                seeds = [p for p in (alg.inputs or [])
                         if p not in byte_slices and p.name == seed_name]
                keep = byte_slices[:1] + seeds
            elif is_buf_transform:
                # A codec is exactly `(in, inlen, out, outlen)`: ONE input slice, ONE output
                # slice. The output `char *out` is NOT const, so it lifts to `&[u8]` (no `mut`)
                # and the mut-heuristic below would wrongly keep it as a phantom second param —
                # the signature/arity mismatch that made smaz's fills unwinnable. Keep only the
                # first byte-slice (the input); the returned Vec replaces `out`.
                keep = byte_slices[:1]
            else:
                # Digest (SipHash/SHA): drop the `&mut` out buffer, keep read-only inputs
                # (message [+ key]).
                keep = [p for p in byte_slices if "mut" not in (p.rust_type or "")]
            if not keep:
                continue
            alg.inputs = keep
            try:
                alg.outputs = []
            except Exception:  # noqa: BLE001
                pass
            alg.return_type = "Vec<u8>"
            n += 1
    return n


_STRUCT_PTR_RE = re.compile(r"^(?:struct\s+)?([A-Za-z_]\w*)\s*\*$")


def classify_scalar_mutator_shape(sig, structs):
    """fn(SingleScalarStruct*, [int extra args...]) -> int|void : a scalar-state mutator.
    The struct is a single scalar field, so state is carried as a bare `&mut <int>`.
    Returns (struct_name, state_param_name, scalar_rust, extra) where extra is a list of
    (arg_name, rust_int_type) for the trailing scalar args, or None if it doesn't fit."""
    from alchemist.verifier import struct_lift as _sl
    params = sig.params or []
    if not params:
        return None
    m = _STRUCT_PTR_RE.match((params[0][1] or "").strip())
    if not m:
        return None
    struct_name = m.group(1)
    scalar_rust = _sl.single_scalar_field(structs.get(struct_name))
    if scalar_rust is None:
        return None
    extra = []
    for pn, pt in params[1:]:
        pr = _sl.c_scalar_to_rust((pt or "").strip())
        if pr is None or pr in ("f32", "f64"):
            return None
        extra.append((pn, pr))
    ret = (sig.return_type or "").strip()
    if ret != "void" and not _INT_C_TYPES.match(ret):
        return None
    return (struct_name, params[0][0], scalar_rust, extra)


def fuzz_scalar_mutator_vectors(dll, alg, sig, info, *, count: int = 40):
    """Drive the C mutator on fuzzed initial state (+ fuzzed extra scalar args), capture
    (return, post-state)."""
    import ctypes
    from alchemist.verifier.struct_lift import c_scalar_to_rust
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    _CT = {
        "u8": ctypes.c_uint8, "i8": ctypes.c_int8, "u16": ctypes.c_uint16,
        "i16": ctypes.c_int16, "u32": ctypes.c_uint32, "i32": ctypes.c_int32,
        "u64": ctypes.c_uint64, "i64": ctypes.c_int64,
        "usize": ctypes.c_size_t, "isize": ctypes.c_ssize_t,
    }
    struct_name, state_param, scalar_rust, extra = info
    state_ct = _CT.get(scalar_rust)
    if state_ct is None:
        return []
    extra_cts = [(nm, rt, _CT.get(rt)) for nm, rt in extra]
    if any(ct is None for _, _, ct in extra_cts):
        return []
    ret_rust = None if (sig.return_type or "").strip() == "void" else c_scalar_to_rust(sig.return_type)
    ret_ct = _CT.get(ret_rust) if ret_rust else None
    try:
        fn = getattr(dll, sig.name)
    except AttributeError:
        return []
    fn.argtypes = (ctypes.POINTER(state_ct),) + tuple(ct for _, _, ct in extra_cts)
    fn.restype = ret_ct

    def _bits(rt):
        return int(rt[1:]) if rt[1:].isdigit() else 64
    smax = (1 << _bits(scalar_rust)) - 1
    rng = _rng(_FUZZ_SEED)
    base = [0, 1, 2, 3, smax, smax - 1, smax // 2, 0x1234567, 0xDEADBEEF, 0xCAFEBABE]
    while len(base) < count:
        base.append(rng.randrange(0, smax + 1))
    extra_spec = ",".join(f"{nm}:{rt}" for nm, rt in extra)
    vectors = []
    for sv in base[:count]:
        cs = state_ct(sv & smax)
        row = {state_param: str(sv & smax)}
        c_args = []
        for nm, rt, ct in extra_cts:
            emax = (1 << _bits(rt)) - 1
            ev = rng.randrange(0, emax + 1)
            row[nm] = str(ev)
            c_args.append(ct(ev))
        try:
            r = fn(ctypes.byref(cs), *c_args)
        except Exception:  # noqa: BLE001
            continue
        new_s = cs.value & smax
        ret_val = (int(r) & smax) if ret_ct is not None else 0
        vectors.append(SpecTestVector(
            description=f"mutator_{sv}",
            source=f"C reference (state mutator): {sig.name}",
            inputs=row,
            expected_output=f"{ret_val}|{new_s}",
            tolerance=f"scalar_mutator|{state_param}|{scalar_rust}|{ret_rust or 'unit'}|{extra_spec}",
        ))
    return vectors


_CONST_BYTE_PTR2 = re.compile(r"^const\s+(unsigned char|uint8_t|char)\s*\*$")
_MUT_BYTE_PTR3 = re.compile(r"^(unsigned char|uint8_t|char)\s*\*$")


def _ct_for(rust):
    import ctypes
    return {
        "u8": ctypes.c_uint8, "i8": ctypes.c_int8, "u16": ctypes.c_uint16,
        "i16": ctypes.c_int16, "u32": ctypes.c_uint32, "i32": ctypes.c_int32,
        "u64": ctypes.c_uint64, "i64": ctypes.c_int64, "usize": ctypes.c_size_t,
    }.get(rust)


def _ctypes_struct_cls(name, fields):
    import ctypes
    from alchemist.verifier.struct_lift import c_scalar_to_rust
    cf = []
    for f in fields:
        if f.is_ptr:
            cf.append((f.name, ctypes.c_void_p)); continue
        base = _ct_for(c_scalar_to_rust(f.ctype))
        if base is None:
            return None
        cf.append((f.name, (base * int(f.arr)) if f.arr is not None else base))
    return type(name + "_C", (ctypes.Structure,), {"_fields_": cf})


def classify_cipher_sequence(by_name, structs):
    """Find init(S*, const byte*, int) + gen(S*, byte*, int) sharing a multi-field,
    pointer-free struct S (RC4/arcfour-shaped stream ciphers). Returns a group dict or None."""
    from alchemist.verifier import struct_lift as _sl
    groups = {}
    for name, sig in by_name.items():
        if not sig.params:
            continue
        m = _STRUCT_PTR_RE.match((sig.params[0][1] or "").strip())
        if not m:
            continue
        sname = m.group(1)
        if sname not in structs:
            continue
        if _sl.single_scalar_field(structs[sname]) is not None:
            continue
        groups.setdefault(sname, []).append((name, sig))
    for sname, fns_ in groups.items():
        fields = structs[sname]
        if any(f.is_ptr for f in fields):
            continue
        init = gen = None
        for name, sig in fns_:
            ps = [(p[1] or "").strip() for p in sig.params]
            ret_void = (sig.return_type or "").strip() == "void"
            if (len(ps) == 3 and _CONST_BYTE_PTR2.match(ps[1])
                    and _INT_C_TYPES.match(ps[2]) and ret_void):
                init = (name, sig)
            elif (len(ps) == 3 and _MUT_BYTE_PTR3.match(ps[1])
                    and _INT_C_TYPES.match(ps[2]) and ret_void):
                gen = (name, sig)
        if init and gen:
            return {
                "struct": sname, "rust": _sl.rust_struct_name(sname),
                "fields": fields, "init": init, "gen": gen,
            }
    return None


def fuzz_cipher_sequence_vectors(dll, group, *, count: int = 10):
    """Drive the compiled C init+gen sequence on fuzzed keys, capturing post-init state
    (state-observer vectors for init) and keystream output (sequence vectors for gen).
    Returns {init_name: [...], gen_name: [...]}."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED, _bytes_to_rust_literal
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    sname, rust = group["struct"], group["rust"]
    fields = group["fields"]
    init_name, init_sig = group["init"]
    gen_name, gen_sig = group["gen"]
    StructC = _ctypes_struct_cls(sname, fields)
    if StructC is None:
        return {}
    try:
        c_init = getattr(dll, init_name)
        c_gen = getattr(dll, gen_name)
    except AttributeError:
        return {}
    c_init.restype = None
    c_init.argtypes = (ctypes.POINTER(StructC), ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int)
    c_gen.restype = None
    c_gen.argtypes = (ctypes.POINTER(StructC), ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int)
    init_key_param = init_sig.params[1][0]
    init_len_param = init_sig.params[2][0]
    gen_key_param = init_key_param  # sequence re-inits with the same key
    gen_len_param = gen_sig.params[2][0]

    def _field_literal(cval, f):
        if f.arr is not None:
            return "[" + ", ".join(f"{int(cval[i])}" for i in range(int(f.arr))) + "]"
        return f"{int(cval)}"

    rng = _rng(_FUZZ_SEED)
    init_vecs, gen_vecs = [], []
    for vi in range(count):
        klen = 1 + (vi % 16) if vi < 6 else rng.randrange(1, 33)
        key = bytes(rng.randrange(0, 256) for _ in range(klen))
        kbuf = (ctypes.c_ubyte * klen)(*key)
        st = StructC()
        try:
            c_init(ctypes.byref(st), kbuf, klen)
        except Exception:  # noqa: BLE001
            continue
        # state-observer vector for init
        field_asserts = "|".join(f"{f.name}:{_field_literal(getattr(st, f.name), f)}" for f in fields)
        init_vecs.append(SpecTestVector(
            description=f"init_klen_{klen}",
            source=f"C reference (post-init state): {init_name}",
            inputs={init_key_param: _bytes_to_rust_literal(key), init_len_param: f"{klen}"},
            expected_output=field_asserts,
            tolerance=f"state_observer|{rust}|{init_name}|{init_key_param}|{init_len_param}",
        ))
        # sequence vector for gen: fresh init then generate
        outlen = rng.randrange(0, 129)
        st2 = StructC()
        c_init(ctypes.byref(st2), kbuf, klen)
        obuf = (ctypes.c_ubyte * outlen)() if outlen else (ctypes.c_ubyte * 0)()
        try:
            c_gen(ctypes.byref(st2), obuf, outlen)
        except Exception:  # noqa: BLE001
            continue
        out = bytes(obuf[i] for i in range(outlen))
        gen_vecs.append(SpecTestVector(
            description=f"seq_klen_{klen}_out_{outlen}",
            source=f"C reference (init+keystream): {gen_name}",
            inputs={gen_key_param: _bytes_to_rust_literal(key), init_len_param: f"{klen}",
                    gen_len_param: f"{outlen}"},
            expected_output=_bytes_to_rust_literal(out),
            tolerance=(f"cipher_seq|{rust}|{init_name}|{gen_key_param}|{init_len_param}"
                       f"|{gen_len_param}"),
        ))
    return {init_name: init_vecs, gen_name: gen_vecs}


def classify_hash_sequence(by_name, structs):
    """Find init(S*) + update(S*, const byte*, int) + final(S*) -> scalar sharing a
    SINGLE-SCALAR struct S (FNV / incremental-hash shaped: reset, absorb bytes, read digest).
    The state is unwrapped to a bare primitive (no FFI struct). Returns a group dict or None."""
    from alchemist.verifier import struct_lift as _sl
    groups = {}
    for name, sig in by_name.items():
        if not sig.params:
            continue
        p0 = re.sub(r"^const\s+", "", (sig.params[0][1] or "").strip())
        m = _STRUCT_PTR_RE.match(p0)
        if not m or m.group(1) not in structs:
            continue
        if _sl.single_scalar_field(structs[m.group(1)]) is None:
            continue
        groups.setdefault(m.group(1), []).append((name, sig))
    for sname, fns_ in groups.items():
        init = update = final = None
        for name, sig in fns_:
            ps = [(p[1] or "").strip() for p in sig.params]
            ret = (sig.return_type or "").strip()
            if len(ps) == 1 and ret == "void":
                init = (name, sig)
            elif (len(ps) == 3 and (_CONST_BYTE_PTR2.match(ps[1]) or _MUT_BYTE_PTR3.match(ps[1]))
                    and _INT_C_TYPES.match(ps[2]) and ret == "void"):
                update = (name, sig)
            elif len(ps) == 1 and ret != "void" and _ctype(ret) is not None:
                final = (name, sig)
        if init and update and final:
            return {
                "struct": sname,
                "prim": _sl.single_scalar_field(structs[sname]),
                "field_ctype": structs[sname][0].ctype,
                "ret_ctype": (final[1].return_type or "").strip(),
                "init": init, "update": update, "final": final,
            }
    return None


def fuzz_hash_sequence_vectors(dll, group, *, count: int = 12):
    """Drive the compiled-C init;update(data);final() sequence on fuzzed data — post-init state
    (init observer), post-update state (update observer), and the digest (final composed).
    Returns {init_name: [...], update_name: [...], final_name: [...]}."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED, _bytes_to_rust_literal
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    prim = group["prim"]
    state_ct = _ctype(group["field_ctype"])
    if state_ct is None:
        return {}
    ret_ct = _ctype(group["ret_ctype"]) or state_ct
    init_name = group["init"][0]
    upd_name, upd_sig = group["update"]
    fin_name = group["final"][0]
    try:
        c_init = getattr(dll, init_name)
        c_upd = getattr(dll, upd_name)
        c_fin = getattr(dll, fin_name)
    except AttributeError:
        return {}
    c_init.restype = None
    c_init.argtypes = (ctypes.POINTER(state_ct),)
    c_upd.restype = None
    c_upd.argtypes = (ctypes.POINTER(state_ct), ctypes.POINTER(ctypes.c_ubyte),
                      _ctype(upd_sig.params[2][1]) or ctypes.c_int)
    c_fin.restype = ret_ct
    c_fin.argtypes = (ctypes.POINTER(state_ct),)
    data_param = upd_sig.params[1][0]
    len_param = upd_sig.params[2][0]
    rng = _rng(_FUZZ_SEED)
    init_vecs, upd_vecs, fin_vecs = [], [], []
    st = state_ct()
    c_init(ctypes.byref(st))
    init_vecs.append(SpecTestVector(
        description="init_basis", source=f"C reference (post-init): {init_name}",
        inputs={}, expected_output=f"{int(st.value)}",
        tolerance=f"hash_init|{prim}|{init_name}"))
    for vi in range(count):
        dlen = vi if vi < 6 else rng.randrange(0, 65)
        data = bytes(rng.randrange(0, 256) for _ in range(dlen))
        dbuf = (ctypes.c_ubyte * dlen)(*data) if dlen else (ctypes.c_ubyte * 0)()
        st2 = state_ct()
        c_init(ctypes.byref(st2))
        c_upd(ctypes.byref(st2), dbuf, dlen)
        upd_vecs.append(SpecTestVector(
            description=f"upd_{dlen}", source=f"C reference (state after update): {upd_name}",
            inputs={data_param: _bytes_to_rust_literal(data), len_param: f"{dlen}"},
            expected_output=f"{int(st2.value)}",
            tolerance=f"hash_update|{prim}|{init_name}|{upd_name}|{data_param}|{len_param}"))
        st3 = state_ct()
        c_init(ctypes.byref(st3))
        c_upd(ctypes.byref(st3), dbuf, dlen)
        digest = int(c_fin(ctypes.byref(st3)))
        fin_vecs.append(SpecTestVector(
            description=f"digest_{dlen}", source=f"C reference (init+update+final): {fin_name}",
            inputs={data_param: _bytes_to_rust_literal(data), len_param: f"{dlen}"},
            expected_output=f"{digest}",
            tolerance=(f"hash_final|{prim}|{init_name}|{upd_name}|{fin_name}"
                       f"|{data_param}|{len_param}")))
    return {init_name: init_vecs, upd_name: upd_vecs, fin_name: fin_vecs}


def _rust_name_from_spec(specs, fn_name, default):
    for module in specs or []:
        for alg in getattr(module, 'algorithms', None) or []:
            if alg.name == fn_name and alg.inputs:
                rn = (alg.inputs[0].rust_type or '').replace('&mut', '').replace('&', '').strip()
                if rn and (rn[0].isalpha() or rn[0] == '_'):
                    return rn
    return default


# A byte BUFFER parameter in a hash context API — accepts the raw C array-declarator
# form (`const BYTE data[]`, `BYTE hash[]`) AND the pointer form, with the BYTE/uint8
# typedef unresolved (signature params are not typedef-expanded like struct fields are).
_HASH_BYTE_BUF = re.compile(
    r"^(?P<const>const\s+)?(BYTE|unsigned\s+char|uint8_t|char|u8|int8_t)\b"
    r"[^,]*?(\[\s*\d*\s*\]|\*)\s*$")


def _is_const_byte_buf(t: str) -> bool:
    m = _HASH_BYTE_BUF.match((t or "").strip())
    return bool(m and m.group("const"))


def _is_mut_byte_buf(t: str) -> bool:
    m = _HASH_BYTE_BUF.match((t or "").strip())
    return bool(m and not m.group("const"))


def _digest_len_from_specs(specs, fn_name) -> "int | None":
    """The digest byte-count for a `final` fn, read from its Rust lift: the extractor
    turns `void final(ctx, BYTE hash[])` into `final(ctx, hash: &mut [u8; N])` — N is
    the digest length (SHA-256=32, SHA-1=20, MD5=16)."""
    for m in specs or []:
        for alg in getattr(m, "algorithms", None) or []:
            if alg.name == fn_name:
                for p in (alg.inputs or []):
                    mm = re.search(r"\[\s*u8\s*;\s*(\d+)\s*\]", p.rust_type or "")
                    if mm:
                        return int(mm.group(1))
    return None


def classify_hash_digest_sequence(by_name, structs, specs=None):
    """CONTEXT-HASH sequence: `init(S*)` + `update(S*, const byte*, int)` +
    `final(S*, byte* out)` sharing a MULTI-FIELD, pointer-free struct S, where
    `final` writes an N-byte DIGEST into an out-buffer (SHA-256/SHA-1/SHA-512/MD5/
    HMAC shape). Distinct from `hash_seq` (FNV: single-scalar state + scalar-returning
    final). Optionally captures a `transform(S*, const block[])` block-compressor.
    Needs `specs` to read the digest length from `final`'s `&mut [u8; N]` lift.
    Returns a group dict or None."""
    from alchemist.verifier import struct_lift as _sl
    groups: dict[str, list] = {}
    for name, sig in by_name.items():
        if not sig.params:
            continue
        m = _STRUCT_PTR_RE.match(re.sub(r"^const\s+", "", (sig.params[0][1] or "").strip()))
        if not m or m.group(1) not in structs:
            continue
        groups.setdefault(m.group(1), []).append((name, sig))
    for sname, fns_ in groups.items():
        fields = structs[sname]
        if _sl.single_scalar_field(fields) is not None:  # single-scalar -> hash_seq
            continue
        if any(f.is_ptr for f in fields):
            continue
        init = update = final = transform = None
        for name, sig in fns_:
            ps = [(p[1] or "").strip() for p in sig.params]
            retv = (sig.return_type or "").strip() == "void"
            if len(ps) == 1 and retv:
                init = (name, sig)
            elif len(ps) == 3 and _is_const_byte_buf(ps[1]) and _INT_C_TYPES.match(ps[2]) and retv:
                update = (name, sig)
            elif len(ps) == 2 and _is_mut_byte_buf(ps[1]) and retv:
                final = (name, sig)
            elif len(ps) == 2 and _is_const_byte_buf(ps[1]) and retv:
                transform = (name, sig)  # transform(ctx, const block[]) — block compressor
        if not (init and update and final):
            continue
        digest_len = _digest_len_from_specs(specs, final[0])
        if digest_len is None:
            continue
        rust = _rust_name_from_spec(specs, init[0], _sl.rust_struct_name(sname))
        return {"struct": sname, "rust": rust, "fields": fields,
                "init": init, "update": update, "final": final,
                "transform": transform, "digest_len": digest_len}
    return None


def _hash_field_asserts(st, fields, var="ctx") -> str:
    """Rust `assert_eq!` lines comparing every carried struct field of `var` against
    the post-run C state `st`. Arrays render as `[a, b, ...]`, scalars as ints."""
    from alchemist.verifier.struct_lift import _safe_field_name
    lines = []
    for f in fields:
        cval = getattr(st, f.name)
        fname = _safe_field_name(f.name)
        if f.arr is not None:
            lit = "[" + ", ".join(str(int(cval[i])) for i in range(int(f.arr))) + "]"
        else:
            lit = str(int(cval))
        lines.append(f'assert_eq!({var}.{fname}, {lit}, "field {fname}");')
    return "\n".join(lines)


def fuzz_hash_digest_sequence_vectors(dll, group, *, count: int = 10):
    """Drive the compiled-C init/update/final (+transform) sequence on fuzzed data and
    author self-contained (`rust_body`) tests per function: init and update are verified
    by their POST-STATE (every ctx field vs C), transform by post-transform state, and
    final by the composed init->update->final DIGEST bytes. Each function is verified in
    isolation-once-its-dependencies-are-filled (init, then transform, then update, then
    final — matching leaf-first fill order). Returns {fn_name: [rust_body vectors]}."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    fields = group["fields"]
    rust = group["rust"]
    dlen = group["digest_len"]
    StructC = _ctypes_struct_cls(group["struct"], fields)
    if StructC is None:
        return {}
    init_name = group["init"][0]
    upd_name, upd_sig = group["update"]
    fin_name = group["final"][0]
    tr = group.get("transform")
    try:
        c_init = getattr(dll, init_name)
        c_upd = getattr(dll, upd_name)
        c_fin = getattr(dll, fin_name)
    except AttributeError:
        return {}
    c_init.restype = None
    c_init.argtypes = (ctypes.POINTER(StructC),)
    c_upd.restype = None
    c_upd.argtypes = (ctypes.POINTER(StructC), ctypes.POINTER(ctypes.c_ubyte),
                      _ctype(upd_sig.params[2][1]) or ctypes.c_size_t)
    c_fin.restype = None
    c_fin.argtypes = (ctypes.POINTER(StructC), ctypes.POINTER(ctypes.c_ubyte))
    c_tr = None
    if tr is not None:
        try:
            c_tr = getattr(dll, tr[0])
            c_tr.restype = None
            c_tr.argtypes = (ctypes.POINTER(StructC), ctypes.POINTER(ctypes.c_ubyte))
        except AttributeError:
            c_tr = None
    # The block size for a transform is the size of the byte-array state field.
    block_len = next((int(f.arr) for f in fields if f.arr is not None
                      and f.ctype in ("unsigned char", "char", "uint8_t")), 64)
    rng = _rng(_FUZZ_SEED)
    init_v, upd_v, fin_v, tr_v = [], [], [], []

    def _data_lit(b: bytes) -> str:
        return "&[" + ", ".join(str(x) for x in b) + "]"

    # init: deterministic — one post-init state observer suffices, but take a couple.
    for i in range(2):
        st = StructC()
        c_init(ctypes.byref(st))
        body = (f"let mut ctx = super::{rust}::default();\n"
                f"super::{init_name}(&mut ctx);\n"
                f"{_hash_field_asserts(st, fields)}")
        init_v.append(SpecTestVector(
            description=f"post_init_{i}", source=f"C reference (post-init state): {init_name}",
            inputs={}, expected_output=body, tolerance="rust_body"))

    for vi in range(count):
        dl = vi if vi < 6 else rng.randrange(0, 200)
        data = bytes(rng.randrange(0, 256) for _ in range(dl))
        dbuf = (ctypes.c_ubyte * dl)(*data) if dl else (ctypes.c_ubyte * 0)()
        # update: post-init+update state observer.
        st = StructC()
        c_init(ctypes.byref(st))
        c_upd(ctypes.byref(st), dbuf, dl)
        body = (f"let mut ctx = super::{rust}::default();\n"
                f"super::{init_name}(&mut ctx);\n"
                f"let data: &[u8] = {_data_lit(data)};\n"
                f"super::{upd_name}(&mut ctx, data);\n"
                f"{_hash_field_asserts(st, fields)}")
        upd_v.append(SpecTestVector(
            description=f"post_update_{dl}", source=f"C reference (post-update state): {upd_name}",
            inputs={}, expected_output=body, tolerance="rust_body"))
        # final: composed init->update->final digest.
        st2 = StructC()
        c_init(ctypes.byref(st2))
        c_upd(ctypes.byref(st2), dbuf, dl)
        out = (ctypes.c_ubyte * dlen)()
        c_fin(ctypes.byref(st2), out)
        digest = bytes(out[i] for i in range(dlen))
        body = (f"let mut ctx = super::{rust}::default();\n"
                f"super::{init_name}(&mut ctx);\n"
                f"let data: &[u8] = {_data_lit(data)};\n"
                f"super::{upd_name}(&mut ctx, data);\n"
                f"let mut out = [0u8; {dlen}];\n"
                f"super::{fin_name}(&mut ctx, &mut out);\n"
                f"assert_eq!(out, [{', '.join(str(x) for x in digest)}], \"digest_dl_{dl}\");")
        fin_v.append(SpecTestVector(
            description=f"digest_dl_{dl}", source=f"C reference (init+update+final): {fin_name}",
            inputs={}, expected_output=body, tolerance="rust_body"))

    # transform: post-init+transform(one block) state observer.
    if c_tr is not None and tr is not None:
        for vi in range(4):
            blk = bytes(rng.randrange(0, 256) for _ in range(block_len))
            bbuf = (ctypes.c_ubyte * block_len)(*blk)
            st = StructC()
            c_init(ctypes.byref(st))
            c_tr(ctypes.byref(st), bbuf)
            body = (f"let mut ctx = super::{rust}::default();\n"
                    f"super::{init_name}(&mut ctx);\n"
                    f"let block: &[u8] = {_data_lit(blk)};\n"
                    f"super::{tr[0]}(&mut ctx, block);\n"
                    f"{_hash_field_asserts(st, fields)}")
            tr_v.append(SpecTestVector(
                description=f"post_transform_{vi}",
                source=f"C reference (post-transform state): {tr[0]}",
                inputs={}, expected_output=body, tolerance="rust_body"))

    out_map = {init_name: init_v, upd_name: upd_v, fin_name: fin_v}
    if tr is not None and tr_v:
        out_map[tr[0]] = tr_v
    return out_map


def classify_alloc_sequence(by_name, structs, specs=None):
    """init(S*, byte*, int) + op(S*, int) -> int, sharing a multi-field struct S
    (bump/arena allocator: init sets a buffer+capacity, op returns offsets/-1). Returns a
    group dict or None. The op's C return is int; the Rust port may lift it to Result."""
    from alchemist.verifier import struct_lift as _sl
    groups = {}
    for name, sig in by_name.items():
        if not sig.params:
            continue
        m = _STRUCT_PTR_RE.match((sig.params[0][1] or "").strip())
        if not m or m.group(1) not in structs:
            continue
        if _sl.single_scalar_field(structs[m.group(1)]) is not None:
            continue
        groups.setdefault(m.group(1), []).append((name, sig))
    for sname, fns_ in groups.items():
        fields = structs[sname]
        init = op = None
        for name, sig in fns_:
            ps = [(p[1] or "").strip() for p in sig.params]
            ret = (sig.return_type or "").strip()
            if (len(ps) == 3 and _CONST_BYTE_PTR2.match(ps[1])
                    and _INT_C_TYPES.match(ps[2]) and ret == "void"):
                init = (name, sig)
            elif (len(ps) == 3 and _MUT_BYTE_PTR3.match(ps[1]) and _INT_C_TYPES.match(ps[2])
                    and ret == "void"):
                init = (name, sig)
            elif len(ps) == 2 and _INT_C_TYPES.match(ps[1]) and _INT_C_TYPES.match(ret):
                op = (name, sig)
        if init and op:
            rust = _rust_name_from_spec(specs, init[0], _sl.rust_struct_name(sname))
            init_kinds = []
            for module in specs or []:
                for alg in getattr(module, "algorithms", None) or []:
                    if alg.name == init[0]:
                        for inp in (alg.inputs or [])[1:]:
                            init_kinds.append("buf" if "[u8]" in (inp.rust_type or "") else "cap")
            return {"struct": sname, "rust": rust, "fields": fields,
                    "init": init, "op": op, "init_kinds": init_kinds}
    return None


def fuzz_alloc_sequence_vectors(dll, group, op_ret_kind="int", init_kinds_csv="buf", *, count: int = 12):
    """Drive init(buffer of size cap) then a sequence of op(n_i), capturing returns. Also
    mint an init state-observer. Returns {init_name: [...], op_name: [...]}."""
    import ctypes
    from alchemist.extractor.fuzz_vectors import _rng, _FUZZ_SEED
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    sname, rust = group["struct"], group["rust"]
    fields = group["fields"]
    init_name = group["init"][0]
    op_name = group["op"][0]
    StructC = _ctypes_struct_cls(sname, fields)
    if StructC is None:
        return {}
    try:
        c_init = getattr(dll, init_name)
        c_op = getattr(dll, op_name)
    except AttributeError:
        return {}
    c_init.restype = None
    c_init.argtypes = (ctypes.POINTER(StructC), ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int)
    c_op.restype = ctypes.c_int
    c_op.argtypes = (ctypes.POINTER(StructC), ctypes.c_int)
    scalar_fields = [f for f in fields if not f.is_ptr and f.arr is None]
    rng = _rng(_FUZZ_SEED)
    init_vecs, seq_vecs = [], []
    for vi in range(count):
        cap = rng.randrange(0, 257)
        buf = (ctypes.c_ubyte * cap)() if cap else (ctypes.c_ubyte * 0)()
        st = StructC()
        try:
            c_init(ctypes.byref(st), buf, cap)
        except Exception:  # noqa: BLE001
            continue
        # init state-observer
        fa = "|".join(f"{f.name}:{int(getattr(st, f.name))}" for f in scalar_fields)
        init_vecs.append(SpecTestVector(
            description=f"init_cap_{cap}",
            source=f"C reference (post-init state): {init_name}",
            inputs={"__cap__": str(cap)},
            expected_output=fa,
            tolerance=f"alloc_init|{rust}|{init_name}|{','.join(f.name for f in scalar_fields)}|{init_kinds_csv}",
        ))
        # op sequence on a fresh init
        st2 = StructC()
        buf2 = (ctypes.c_ubyte * cap)() if cap else (ctypes.c_ubyte * 0)()
        c_init(ctypes.byref(st2), buf2, cap)
        ns = [rng.randrange(-2, cap + 8) for _ in range(rng.randrange(1, 7))]
        outs = []
        for n in ns:
            try:
                outs.append(int(c_op(ctypes.byref(st2), n)))
            except Exception:  # noqa: BLE001
                outs.append(-1)
        seq_vecs.append(SpecTestVector(
            description=f"seq_cap_{cap}",
            source=f"C reference (init+op sequence): {op_name}",
            inputs={"__cap__": str(cap), "__ns__": ",".join(str(x) for x in ns)},
            expected_output=",".join(str(x) for x in outs),
            tolerance=f"alloc_seq|{rust}|{init_name}|{op_name}|{op_ret_kind}|{init_kinds_csv}",
        ))
    return {init_name: init_vecs, op_name: seq_vecs}


def build_diff_config(
    c_source_dir: Path,
    specs: list | None,
) -> DifferentialConfig | None:
    """Derive a DifferentialConfig for a subject from its headers + specs.

    Returns None when nothing can be configured (no specs, or no algorithm
    matches a recognized shape) — the differential gate then refuses, which
    is the correct fail-closed outcome for an unconfigurable subject.
    """
    c_source_dir = Path(c_source_dir)
    if not specs:
        return None
    signatures = collect_subject_signatures(c_source_dir)
    if not signatures:
        return None
    by_name = {s.name: s for s in signatures}

    harnesses: list[AlgorithmHarness] = []
    used_signatures: list[CSignature] = []
    _structs = struct_lift.structs_in_dir(c_source_dir)
    _typedef_overrides: dict[str, str] = {}
    _struct_defs: list[str] = []
    _as = classify_alloc_sequence(by_name, _structs, specs)
    if _as is not None:
        _affi = struct_lift.emit_ffi_struct(_as["rust"], _as["fields"])
        if _affi is not None:
            _struct_defs.append(_affi)
            _typedef_overrides[_as["struct"]] = _as["rust"]
            _opn = _as["op"][0]
            harnesses.append(AlgorithmHarness(
                algorithm=_opn,
                category="alloc_seq",
                rust_call=f"rust_{_opn}(cap, ns.clone())",
                c_call=f"c_{_opn}(cap, ns)",
                cases=2000,
                input_strategy="(0usize..256, prop::collection::vec(0usize..300, 1..8))",
                seq_struct=_as["rust"], seq_init=_as["init"][0], seq_gen=_opn,
                init_kinds=_as.get("init_kinds") or ["buf"],
            ))
            used_signatures.append(by_name[_as["init"][0]])
            used_signatures.append(by_name[_opn])
    _cs = classify_cipher_sequence(by_name, _structs)
    if _cs is not None:
        _ffi = struct_lift.emit_ffi_struct(_cs["rust"], _cs["fields"])
        if _ffi is not None:
            _struct_defs.append(_ffi)
            _typedef_overrides[_cs["struct"]] = _cs["rust"]
            _gen_name = _cs["gen"][0]
            harnesses.append(AlgorithmHarness(
                algorithm=_gen_name,
                category="cipher_seq",
                rust_call=f"rust_{_gen_name}(key.clone(), outlen)",
                c_call=f"c_{_gen_name}(key, outlen)",
                cases=2000,
                input_strategy="(prop::collection::vec(any::<u8>(), 1..64), 0usize..256)",
                seq_struct=_cs["rust"], seq_init=_cs["init"][0], seq_gen=_gen_name,
            ))
            used_signatures.append(by_name[_cs["init"][0]])
            used_signatures.append(by_name[_gen_name])
    _hs = classify_hash_sequence(by_name, _structs)
    if _hs is not None:
        _fin = _hs["final"][0]
        _hret = struct_lift.c_scalar_to_rust(_hs["ret_ctype"]) or _hs["prim"]
        _typedef_overrides[_hs["struct"]] = _hs["prim"]
        harnesses.append(AlgorithmHarness(
            algorithm=_fin,
            category="hash_seq",
            rust_call=f"rust_{_fin}(data.clone())",
            c_call=f"c_{_fin}(data)",
            cases=2000,
            input_strategy="prop::collection::vec(any::<u8>(), 0..128)",
            state_rust=_hs["prim"],
            seq_init=_hs["init"][0],
            seq_gen=_hs["update"][0],
            hash_ret=_hret,
        ))
        used_signatures.append(by_name[_hs["init"][0]])
        used_signatures.append(by_name[_hs["update"][0]])
        used_signatures.append(by_name[_fin])
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            # The C signature shape is the real gate — a scalar-returning
            # byte-slice function is differentially verifiable whether the
            # extractor labelled it checksum or hash (FNV, CRC-16, ...). A
            # true digest-returning hash fails classify_checksum_shape (its
            # return type isn't a scalar int), so it's excluded here.
            sig = by_name.get(alg.name)
            if sig is None:
                continue
            # A codec the extractor labelled compression/decompression is still a
            # buf_transform whose byte-exact differential harness (with encoder
            # round-trip for decoders) IS built below — do NOT skip it, or the
            # final gate gets no config and refuses a fully-translated codec.
            # Likewise a `char* f(char*)` text transform the extractor labelled
            # "cipher" (rot13 IS a substitution cipher) is a clean cstr_out shape
            # with a sound differential — the semantic label must not starve the
            # gate. Only ciphers/compression that fit NEITHER shape are skipped.
            if (alg.category or "") in ("cipher", "compression", "decompression") \
                    and classify_buf_transform(sig) is None \
                    and classify_cstr_out(sig) is None:
                continue
            if _cs is not None and alg.name in (_cs['init'][0], _cs['gen'][0]):
                continue
            if _as is not None and alg.name in (_as['init'][0], _as['op'][0]):
                continue
            if _hs is not None and alg.name in (_hs['init'][0], _hs['update'][0], _hs['final'][0]):
                continue
            _mut = classify_scalar_mutator_shape(sig, _structs)
            if _mut is not None:
                _sname, _sparam, _srust, _extra = _mut
                _anames = ["a_state"] + [f"a_{_i}" for _i in range(len(_extra))]
                _atypes = [_srust] + [rt for _, rt in _extra]
                if _extra:
                    _strat = "(" + ", ".join(f"any::<{t}>()" for t in _atypes) + ")"
                    _bind = "(" + ", ".join(_anames) + ")"
                else:
                    _strat = f"any::<{_srust}>()"
                    _bind = "a_state"
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="scalar_mutator",
                    rust_call="rust_" + alg.name + "(" + ", ".join(_anames) + ")",
                    c_call="c_" + alg.name + "(" + ", ".join(_anames) + ")",
                    cases=4000,
                    input_strategy=_strat,
                    state_rust=_srust,
                    mutator_bind=_bind,
                    mutator_arg_types=[rt for _, rt in _extra],
                ))
                _typedef_overrides[_sname] = _srust
                used_signatures.append(sig)
                continue
            if classify_inplace_shape(sig) is not None:
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="inplace",
                    rust_call=f"rust_{alg.name}(input.clone())",
                    c_call=f"c_{alg.name}(input)",
                    cases=2000,
                    input_strategy="prop::collection::vec(any::<u8>(), 0..256)",
                ))
                used_signatures.append(sig)
                continue
            _iar = classify_iarray_reduce(sig)
            if _iar is not None:
                # `<scalar> f(const T* a, int n)` — an int-array reduction. The Rust
                # fn is `(&[T]) -> R`; the C side passes ptr+len. Element values are
                # bounded so the C reduction can't hit signed-overflow UB.
                _erust = _iar["elem_rust"]
                _lo, _hi = _elem_range(_erust)
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="iarray_reduce",
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call=f"c_{alg.name}(&input)",
                    input_strategy=(
                        f"prop::collection::vec({_lo}{_erust}..={_hi}{_erust}, 0..64)"),
                    state_rust=_erust,
                    cases=4000,
                ))
                used_signatures.append(sig)
                continue
            _bg = classify_buf_gen(sig)
            if _bg is not None:
                # `<byteptr> f(<size> n, <scalar>...)` -> Rust `(usize, ...) -> Vec<u8>`.
                # proptest binds (n, a0, ...); the wrappers read n bytes back and compare.
                _bg_extra = [(struct_lift.c_scalar_to_rust(e) or "u8") for e in _bg]
                _bg_names = ["n"] + [f"a{_i}" for _i in range(len(_bg_extra))]
                _bg_args = ", ".join(_bg_names)
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="buf_gen",
                    rust_call=f"rust_{alg.name}({_bg_args})",
                    c_call=f"c_{alg.name}({_bg_args})",
                    scalar_arg_types=_bg_extra,
                    cases=4000,
                ))
                used_signatures.append(sig)
                continue
            if classify_scalar_shape(sig) is not None:
                _sargs = [(i.rust_type or "u64").strip() for i in (alg.inputs or [])] or ["u64"]
                _snames = [f"a{_i}" for _i in range(len(_sargs))]
                # Match the differential's fuzz domain to the fill oracle: when
                # ALCHEMIST_SAFE_SCALAR is set (contract-domain / ctype fns), bound
                # each int arg to the safe char domain instead of any::<T>() so the
                # proptest doesn't drive the C reference into UB (a segfault would
                # abort the test binary). Both sides then test the same [-1,255].
                import os as _os2
                _safe = bool(_os2.environ.get("ALCHEMIST_SAFE_SCALAR"))

                def _one_strat(t):
                    if _safe:
                        _lo = "-1" if t.startswith("i") else "0"
                        return f"({_lo}{t}..=255{t})"
                    return f"any::<{t}>()"
                if len(_sargs) == 1:
                    _sstrat = _one_strat(_sargs[0])
                    _sbind = _snames[0]
                else:
                    _sstrat = "(" + ", ".join(_one_strat(t) for t in _sargs) + ")"
                    _sbind = "(" + ", ".join(_snames) + ")"
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="scalar",
                    rust_call=f"rust_{alg.name}(" + ", ".join(_snames) + ")",
                    c_call=f"c_{alg.name}(" + ", ".join(_snames) + ")",
                    cases=4000,
                    input_strategy=_sstrat,
                    scalar_arg_types=_sargs,
                    mutator_bind=_sbind,
                ))
                used_signatures.append(sig)
                continue
            _rt_enc = classify_cstr_roundtrip(sig, by_name)
            if _rt_enc is not None:
                # DECODER `char* f(char*)` paired with an encoder — verify the
                # roundtrip identity decode(encode(pt)) == pt. The C side is the
                # ENCODER (uniquely-named c_<decoder>_enc wrapper), so no lossy
                # C-decoder call is needed; the proptest mints a valid stream
                # from random plaintext and requires the Rust decoder to invert
                # it byte-exactly. Checked BEFORE cstr_out (shared signature).
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="cstr_roundtrip",
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call="",
                    encoder_c_call=f"c_{alg.name}_enc(&pt)",
                    # ASCII plaintext (1..=127): a signed-char encoder has UB on
                    # high bytes (see fuzz_cstr_roundtrip_vectors) — keep it in
                    # its defined domain so the roundtrip identity holds.
                    input_strategy="prop::collection::vec(1u8..=127u8, 0..48)",
                    cases=2000,
                ))
                used_signatures.append(sig)
                if _rt_enc in by_name and by_name[_rt_enc] not in used_signatures:
                    used_signatures.append(by_name[_rt_enc])
                continue
            if classify_cstr_out(sig) is not None:
                # C `char* f(char*)`: string in -> freshly-allocated string out
                # (to_upper / rot13 / hex_encode / *_encode). Checked before
                # cbuf_out (its 1-param shape is disjoint from cbuf_out's 2-param
                # shape, but this mirrors synthesize_c_vectors' dispatch order).
                # Without this branch the final differential gate found no harness
                # for a byte-exact-verified text transform and refused it —
                # the "verified-function but workspace-FAIL" gap the leaf
                # benchmark (P0.11) surfaced.
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="cstr_out",
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call=f"c_{alg.name}(&input)",
                    input_strategy=r'"[ -~]{0,48}"',
                    cases=4000,
                ))
                used_signatures.append(sig)
                continue
            if classify_cbuf_out(sig) is not None:
                # C-string in -> result-string out (NMEA). The differential fuzzes an input
                # string and compares the two result strings.
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="cbuf_out",
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call=f"c_{alg.name}(&input)",
                    cases=4000,
                ))
                used_signatures.append(sig)
                continue
            shape = classify_checksum_shape(sig)
            if shape is not None:
                boundaries = (_ADLER_BOUNDARIES if "adler" in alg.name.lower()
                              else _GENERIC_BOUNDARIES)
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="checksum",
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call=f"c_{alg.name}(&input)",
                    seed=(default_seed(alg.name)
                          if shape in ("seeded", "seeded_trailing") else None),
                    seed_trailing=(shape == "seeded_trailing"),
                    boundary_lengths=list(boundaries),
                    cases=5000,
                ))
                used_signatures.append(sig)
                continue
            digest = classify_digest_shape(sig)
            if digest is not None:
                # Byte-digest hash (SipHash / SHA / HMAC family). Key and
                # digest length are baked into the wrappers, so the harness
                # fuzzes the message and compares digest bytes.
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="hash",
                    digest=True,
                    key=canonical_key(digest.key_len) if digest.key_idx is not None
                        else None,
                    digest_len=digest.digest_len,
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call=f"c_{alg.name}(&input)",
                    boundary_lengths=list(_GENERIC_BOUNDARIES),
                    cases=5000,
                ))
                used_signatures.append(sig)
                continue
            # Checked LAST (after digest): a variable-length buffer transform (codec) — its
            # signature `int f(byteptr, int, byteptr, int)` overlaps a fixed-output digest, so
            # digest (more specific) wins first; anything left that fits is a variable codec.
            if classify_buf_transform(sig) is not None:
                # If this is a DECODER whose paired ENCODER is also in the
                # subject, fuzz it round-trip: random plaintext -> C encoder ->
                # valid stream -> decode. Decoding random bytes would compare
                # C's undefined-behavior-on-malformed-input against safe Rust.
                _enc = _paired_encoder_name(alg.name)
                _enc_call = f"c_{_enc}(&pt)" if (_enc and _enc in by_name) else None
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="buf_transform",
                    rust_call=f"rust_{alg.name}(&input)",
                    c_call=f"c_{alg.name}(&input)",
                    boundary_lengths=list(_GENERIC_BOUNDARIES),
                    cases=4000,
                    encoder_c_call=_enc_call,
                ))
                used_signatures.append(sig)
                continue
            _cse = classify_cstr_scalar(sig)
            if _cse is not None:
                # `<scalar> f(const char* s, ...scalars)` — string + scalars -> scalar
                # (count_char, char-index, strlen-with-flags). Checked LAST so the
                # byte-buffer shapes (checksum/digest/buf_transform) claim a
                # `(char*, len)` first; this catches the string+char / bare-string
                # leftovers that carry a sound differential.
                # Map a `char` value-arg to i8 (as normalize_char_scalar_params does
                # for the model's fn). The verify stage can hold a pre-normalization
                # spec, so coerce here too — the proptest scalar type MUST match the
                # wrapper's (which adapter_gen derives from the normalized model source).
                _sc_extra = ["i8" if (p.rust_type or "").strip() == "char"
                             else (p.rust_type or "i32").strip()
                             for p in (alg.inputs or [])
                             if not ("str" in (p.rust_type or "").lower()
                                     or "[u8]" in (p.rust_type or ""))]
                # proptest binds (s, a0, a1, ...); the wrappers take (&str, T0, ...).
                _sc_args = ", ".join(["&s"] + [f"a{_i}" for _i in range(len(_sc_extra))])
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="cstr_scalar",
                    rust_call=f"rust_{alg.name}({_sc_args})",
                    c_call=f"c_{alg.name}({_sc_args})",
                    scalar_arg_types=_sc_extra,
                    cases=4000,
                ))
                used_signatures.append(sig)
                continue
    if not harnesses:
        return None

    from alchemist.verifier.build_c_dll import discover_c_build
    c_sources, _c_inc_dirs = discover_c_build(c_source_dir)
    if not c_sources:
        return None
    subject = c_source_dir.name.lower() or "subject"
    return DifferentialConfig(
        c_sources=c_sources,
        c_include_dirs=_c_inc_dirs,
        c_public_signatures=used_signatures,
        c_typedefs=TypedefMap(entries=dict(_typedef_overrides)),
        c_opaque_types=set(),
        c_struct_defs=list(_struct_defs),
        harnesses=harnesses,
        ffi_crate_name=f"c_{re.sub(r'[^a-z0-9_]', '_', subject)}_ref",
    )


def fuzz_checksum_vectors(dll, alg, sig, *, count: int = 24):
    """Mint fill-loop vectors for a scalar-returning byte function (checksum / scalar
    parser / bytewise reducer): {data} -> scalar. Uses the compiled C as the oracle."""
    from alchemist.extractor.fuzz_vectors import (
        _bytes_to_rust_literal, _gen_byte_inputs, _rng, _FUZZ_SEED,
    )
    from alchemist.extractor.schemas import TestVector as SpecTestVector
    shape = classify_checksum_shape(sig)
    if shape is None:
        return []
    binding = _binding_for(sig, shape, default_seed(alg.name))
    fn = binding.load(dll)
    slice_params = [p for p in (alg.inputs or []) if "[u8]" in (p.rust_type or "")]
    if not slice_params:
        return []
    data_param = slice_params[0].name
    # If the Rust fn keeps an explicit length param (not folded into the slice),
    # the fill-test call needs it = the buffer length; otherwise the test would
    # call the fn with a wrong/default length and never match the C oracle.
    len_params = [pp for pp in (alg.inputs or [])
                  if pp.name != data_param and "usize" in (pp.rust_type or "")]
    len_param = len_params[0].name if len_params else None
    # A seeded checksum keeps a seed param (u8..u64, NOT the usize length). The
    # oracle bakes default_seed(); the emitted fill-test must pass that SAME seed
    # value or the call won't match the C reference (and, for a trailing seed,
    # the test would drop the arg entirely -> won't even compile).
    _seed_val = default_seed(alg.name)
    seed_params = [pp for pp in (alg.inputs or [])
                   if pp.name not in (data_param, len_param)
                   and re.fullmatch(r"[iu](8|16|32|64|128|size)", (pp.rust_type or "").strip())
                   and "usize" not in (pp.rust_type or "")]
    seed_param = seed_params[0] if (shape in ("seeded", "seeded_trailing") and seed_params) else None
    rng = _rng(_FUZZ_SEED)
    vectors = []
    for data in _gen_byte_inputs(rng, count):
        try:
            out = binding.adapter(fn, bytes(data))
        except Exception:  # noqa: BLE001
            continue
        _row = {data_param: _bytes_to_rust_literal(bytes(data))}
        if len_param:
            _row[len_param] = f"{len(data)}usize"
        if seed_param is not None:
            _row[seed_param.name] = f"{_seed_val}{(seed_param.rust_type or 'u32').strip()}"
        vectors.append(SpecTestVector(
            description=f"fuzz_input_len_{len(data)}",
            source=f"C reference (scalar): {sig.name}",
            inputs=_row,
            expected_output=str(int(out)),
            tolerance="exact",
        ))
    return vectors


def synthesize_c_vectors(c_source_dir, specs, *, compiler: str = "gcc") -> int:
    """Auto-oracle: mint fuzz vectors by running the compiled C reference in-process.

    CRASH ISOLATION: the oracle calls arbitrary C via ctypes with fuzzed inputs, and
    real C is full of undefined behavior on out-of-domain inputs (e.g. glibc
    `isdigit(c)`/`tolower(c)` index `__ctype_b_loc()[c]` out of bounds and SEGFAULT
    for c outside [-1,255]; div-by-zero; bad pointers). An in-process segfault would
    take down the whole translator. On POSIX we run the fuzzing in a FORKED child:
    if it crashes (killed by a signal), the parent catches it and returns 0 — the
    subject simply gets no auto-oracle vectors (fail-closed: those functions can't be
    verified and are refused, never falsely passed). Windows (no fork, forgiving
    ctype) runs in-process."""
    import os as _os
    if _os.name != "posix" or not hasattr(_os, "fork"):
        return _synthesize_c_vectors_impl(c_source_dir, specs, compiler=compiler)
    import pickle as _pickle
    import tempfile as _tf
    _tmp = _tf.NamedTemporaryFile(delete=False, suffix=".alchvec.pkl")
    _tmp.close()
    _pid = _os.fork()
    if _pid == 0:  # ---- child: isolated so a UB segfault can't kill the parent ----
        try:
            n = _synthesize_c_vectors_impl(c_source_dir, specs, compiler=compiler)
            out = {}
            for mi, m in enumerate(specs):
                for ai, alg in enumerate(getattr(m, "algorithms", None) or []):
                    tv = getattr(alg, "test_vectors", None)
                    if tv:
                        out[(mi, ai)] = tv
            with open(_tmp.name, "wb") as fh:
                _pickle.dump((n, out), fh)
            _os._exit(0)
        except BaseException:  # noqa: BLE001
            _os._exit(70)
    # ---- parent ----
    _, status = _os.waitpid(_pid, 0)
    crashed = _os.WIFSIGNALED(status) or (
        _os.WIFEXITED(status) and _os.WEXITSTATUS(status) != 0)
    try:
        if crashed:
            return 0  # C oracle crashed on a fuzzed input — no vectors, fail-closed
        with open(_tmp.name, "rb") as fh:
            n, out = _pickle.load(fh)
    except Exception:  # noqa: BLE001
        return 0
    finally:
        try:
            _os.unlink(_tmp.name)
        except OSError:
            pass
    for (mi, ai), tv in out.items():
        try:
            specs[mi].algorithms[ai].test_vectors = tv
        except Exception:  # noqa: BLE001
            pass
    return n


def _synthesize_c_vectors_impl(c_source_dir, specs, *, compiler: str = "gcc") -> int:
    """In-process auto-oracle (see synthesize_c_vectors for the crash-isolation wrapper)."""
    import os as _os, ctypes
    from alchemist.verifier.auto_ffi import build_c_dll
    cdir = Path(c_source_dir)
    try:
        signatures = collect_subject_signatures(cdir)
    except Exception:  # noqa: BLE001
        return 0
    if not signatures:
        return 0
    by_name = {s.name: s for s in signatures}
    _structs = struct_lift.structs_in_dir(cdir)
    from alchemist.verifier.build_c_dll import discover_c_build
    c_files, _inc_dirs = discover_c_build(cdir)
    if not c_files:
        return 0
    work = cdir / ".alchemist" / "cvec"
    work.mkdir(parents=True, exist_ok=True)
    dll_path = work / ("cref.dll" if _os.name == "nt" else "libcref.so")
    build = build_c_dll(c_files, dll_path, include_dirs=_inc_dirs, compiler=compiler)
    if not build.success:
        return 0
    try:
        dll = ctypes.CDLL(str(dll_path))
    except OSError:
        return 0
    augmented = 0
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            if getattr(alg, "test_vectors", None):
                continue
            sig = by_name.get(alg.name)
            if sig is None:
                continue
            if classify_checksum_shape(sig) is not None:
                vecs = fuzz_checksum_vectors(dll, alg, sig)
            elif classify_hash_out_shape(sig) is not None:
                vecs = fuzz_hash_out_vectors(dll, alg, sig)
            elif classify_digest_shape(sig) is not None:
                vecs = fuzz_digest_vectors(dll, alg, sig)
                # Second, independent proof: attach the NIST/FIPS catalog KATs, but only the
                # ones the subject's compiled C actually reproduces (canonical, not a variant).
                vecs = list(vecs) + fuzz_digest_catalog_vectors(dll, alg, sig)
            elif classify_scalar_shape(sig) is not None:
                vecs = fuzz_scalar_vectors(dll, alg, sig)
            elif classify_inplace_shape(sig) is not None:
                vecs = fuzz_inplace_vectors(dll, alg, sig)
            elif classify_iarray_reduce(sig) is not None:
                vecs = fuzz_iarray_reduce_vectors(dll, alg, sig)
            elif classify_buf_gen(sig) is not None:
                vecs = fuzz_buf_gen_vectors(dll, alg, sig)
            elif (_rt_enc := classify_cstr_roundtrip(sig, by_name)) is not None:
                vecs = fuzz_cstr_roundtrip_vectors(dll, alg, sig, _rt_enc)
            elif classify_cstr_out(sig) is not None:
                vecs = fuzz_cstr_out_vectors(dll, alg, sig)
            elif classify_cbuf_out(sig) is not None:
                vecs = fuzz_cbuf_out_vectors(dll, alg, sig)
            elif classify_cstr_scalar(sig) is not None:
                vecs = fuzz_cstr_scalar_vectors(dll, alg, sig)
            elif classify_buf_transform(sig) is not None:
                vecs = fuzz_buf_transform_vectors(dll, alg, sig)
            elif (_mi := classify_scalar_mutator_shape(sig, _structs)) is not None:
                vecs = fuzz_scalar_mutator_vectors(dll, alg, sig, _mi)
            else:
                vecs = []
            if vecs:
                alg.test_vectors = vecs
                augmented += 1
    # Stateful cipher sequence (init + keystream sharing a struct): attach state-observer
    # vectors to init and init->keystream sequence vectors to the generator.
    try:
        _ag = classify_alloc_sequence(by_name, _structs, specs)
        if _ag is not None:
            _opret = "int"
            for _m in specs:
                for _al in getattr(_m, "algorithms", None) or []:
                    if _al.name == _ag["op"][0] and "Result" in (getattr(_al, "return_type", "") or ""):
                        _opret = "result"
            _abyfn = fuzz_alloc_sequence_vectors(dll, _ag, _opret, ",".join(_ag.get("init_kinds") or ["buf"]))
            for module in specs:
                for alg in getattr(module, "algorithms", None) or []:
                    if alg.name in _abyfn and _abyfn[alg.name] and not getattr(alg, "test_vectors", None):
                        alg.test_vectors = _abyfn[alg.name]
                        augmented += 1
    except Exception:  # noqa: BLE001
        pass
    try:
        _grp = classify_cipher_sequence(by_name, _structs)
        if _grp is not None:
            _byfn = fuzz_cipher_sequence_vectors(dll, _grp)
            for module in specs:
                for alg in getattr(module, "algorithms", None) or []:
                    if alg.name in _byfn and _byfn[alg.name] and not getattr(alg, "test_vectors", None):
                        alg.test_vectors = _byfn[alg.name]
                        augmented += 1
    except Exception:  # noqa: BLE001
        pass
    try:
        _hg = classify_hash_sequence(by_name, _structs)
        if _hg is not None:
            _hbyfn = fuzz_hash_sequence_vectors(dll, _hg)
            for module in specs:
                for alg in getattr(module, "algorithms", None) or []:
                    if alg.name in _hbyfn and _hbyfn[alg.name] and not getattr(alg, "test_vectors", None):
                        alg.test_vectors = _hbyfn[alg.name]
                        augmented += 1
    except Exception:  # noqa: BLE001
        pass
    # Context-hash digest sequence (SHA-256/SHA-1/MD5/HMAC): multi-field ctx +
    # final(ctx, out_digest). init/update/transform verified by post-state, final
    # by the composed digest — all as self-contained rust_body tests.
    try:
        _dg = classify_hash_digest_sequence(by_name, _structs, specs)
        if _dg is not None:
            _dbyfn = fuzz_hash_digest_sequence_vectors(dll, _dg)
            for module in specs:
                for alg in getattr(module, "algorithms", None) or []:
                    if alg.name in _dbyfn and _dbyfn[alg.name] and not getattr(alg, "test_vectors", None):
                        alg.test_vectors = _dbyfn[alg.name]
                        augmented += 1
    except Exception:  # noqa: BLE001
        pass
    return augmented
