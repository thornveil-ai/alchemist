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

_INT_C_TYPES = re.compile(
    r"^(unsigned|unsigned int|unsigned long|unsigned short|int|long|"
    r"uint8_t|uint16_t|uint32_t|uint64_t|size_t|uInt|uLong|z_size_t)$"
)
_BYTE_PTR = re.compile(r"^(const\s+)?(unsigned char|uint8_t|Bytef|u_char)\s*\*$")
# A read-only byte/opaque input pointer (hash APIs often take `const void *`).
_CONST_IN_PTR = re.compile(
    r"^const\s+(unsigned char|uint8_t|Bytef|u_char|void)\s*\*$")
# A writable output byte buffer.
_MUT_BYTE_PTR = re.compile(r"^(unsigned char|uint8_t|u_char)\s*\*$")
_SIZE_T = re.compile(r"^(const\s+)?(size_t|z_size_t|unsigned long|uInt|uLong)$")

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
}


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


def classify_digest_shape(sig: CSignature) -> "DigestShape | None":
    """Recognize a byte-digest hash (SipHash / SHA / HMAC family)."""
    if (sig.return_type or "").strip() != "int":
        return None
    types = [t.strip() for _, t in sig.params]
    # Unkeyed: (const in*, inlen, mut out*, outlen)
    if (len(types) == 4 and _CONST_IN_PTR.match(types[0]) and _SIZE_T.match(types[1])
            and _MUT_BYTE_PTR.match(types[2]) and _SIZE_T.match(types[3])):
        return DigestShape(in_idx=0, inlen_idx=1, out_idx=2, outlen_idx=3,
                           key_idx=None, key_len=0,
                           digest_len=_DEFAULT_DIGEST_LEN)
    # Keyed: (const in*, inlen, const key*, mut out*, outlen)
    if (len(types) == 5 and _CONST_IN_PTR.match(types[0]) and _SIZE_T.match(types[1])
            and _CONST_IN_PTR.match(types[2]) and _MUT_BYTE_PTR.match(types[3])
            and _SIZE_T.match(types[4])):
        return DigestShape(in_idx=0, inlen_idx=1, out_idx=3, outlen_idx=4,
                           key_idx=2, key_len=_DEFAULT_KEY_LEN,
                           digest_len=_DEFAULT_DIGEST_LEN)
    return None


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


def collect_subject_signatures(c_source_dir: Path) -> list[CSignature]:
    sigs: list[CSignature] = []
    seen: set[str] = set()
    for header in sorted(Path(c_source_dir).glob("*.h")):
        for sig in parse_header(header.read_text(encoding="utf-8",
                                                 errors="replace")):
            if sig.name not in seen:
                seen.add(sig.name)
                sigs.append(sig)
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
        if (alg.category or "") not in ("checksum", "hash"):
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
        vectors.append(SpecTestVector(
            description=f"fuzz_input_len_{len(data)}",
            source=f"C reference (digest): {sig.name}",
            inputs=row,
            expected_output=f"Ok({digest_lit})",
            tolerance="exact",
        ))
    return vectors


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
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            # The C signature shape is the real gate — a scalar-returning
            # byte-slice function is differentially verifiable whether the
            # extractor labelled it checksum or hash (FNV, CRC-16, ...). A
            # true digest-returning hash fails classify_checksum_shape (its
            # return type isn't a scalar int), so it's excluded here.
            if (alg.category or "") not in ("checksum", "hash"):
                continue
            sig = by_name.get(alg.name)
            if sig is None:
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
                    seed=default_seed(alg.name) if shape == "seeded" else None,
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
    if not harnesses:
        return None

    c_sources = sorted(
        f for f in c_source_dir.glob("*.c")
        if "test" not in f.name.lower() and "example" not in f.name.lower()
    )
    if not c_sources:
        return None
    subject = c_source_dir.name.lower() or "subject"
    return DifferentialConfig(
        c_sources=c_sources,
        c_include_dirs=[c_source_dir],
        c_public_signatures=used_signatures,
        c_typedefs=TypedefMap(),
        c_opaque_types=set(),
        harnesses=harnesses,
        ffi_crate_name=f"c_{re.sub(r'[^a-z0-9_]', '_', subject)}_ref",
    )
