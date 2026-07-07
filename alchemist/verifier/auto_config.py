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
_BYTE_PTR = re.compile(r"^(const\s+)?(unsigned char|uint8_t|Bytef|u_char|char)\s*\*$")
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


# Top-level C function definition: `<ret> <name>(<params>) {` starting at column 0.
# Anchoring at line start skips indented body statements (return/if/for...), which is
# what a header prototype parser cannot do on a .c file.
_C_DEF_RE = re.compile(
    r"^(?P<ret>(?:[A-Za-z_]\w*[\s\*]+)+?)(?P<name>[A-Za-z_]\w*)\s*"
    r"\((?P<params>[^;{}]*)\)\s*\{",
    re.MULTILINE,
)
_C_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "do", "else"}


def _parse_c_definitions(c_text: str):
    from alchemist.verifier.auto_ffi import _strip_comments, _parse_params
    text = _strip_comments(c_text)
    out = []
    for m in _C_DEF_RE.finditer(text):
        name = m.group("name")
        if name in _C_KEYWORDS:
            continue
        ret = m.group("ret").strip()
        for kw in ("static", "inline", "extern", "ZEXTERN", "ZEXPORT"):
            ret = re.sub(rf"\b{kw}\b", "", ret).strip()
        if not ret or name.startswith("_"):
            pass
        params = _parse_params(m.group("params").strip())
        out.append(CSignature(name=name, return_type=ret, params=params))
    return out


def collect_subject_signatures(c_source_dir: Path) -> list[CSignature]:
    sigs: list[CSignature] = []
    seen: set[str] = set()
    src = Path(c_source_dir)
    for header in sorted(src.glob("*.h")):
        for sig in parse_header(header.read_text(encoding="utf-8", errors="replace")):
            if sig.name not in seen:
                seen.add(sig.name)
                sigs.append(sig)
    # Headerless single-file subjects (arbitrary cold C): parse top-level function
    # DEFINITIONS from .c files directly (skipping body statements).
    for cfile in sorted(src.glob("*.c")):
        for sig in _parse_c_definitions(cfile.read_text(encoding="utf-8", errors="replace")):
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
        vectors.append(SpecTestVector(
            description=f"fuzz_input_len_{len(data)}",
            source=f"C reference (digest): {sig.name}",
            inputs=row,
            expected_output=f"Ok({digest_lit})",
            tolerance="exact",
        ))
    return vectors


def classify_scalar_shape(sig) -> str | None:
    """All-scalar signature: every param is an int type and the return is an int.
    e.g. isqrt(unsigned)->unsigned, popcount(unsigned long)->int. -> 'scalar' | None."""
    if not _ctype(sig.return_type or ""):
        return None
    params = [t.strip() for _, t in sig.params]
    if not params:
        return None
    if all(_INT_C_TYPES.match(p) for p in params):
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

    def _range(rust_type):
        rt = (rust_type or "u64").strip()
        signed = rt.startswith("i")
        w = 64
        mm = re.search(r"(8|16|32|64|128)", rt)
        if mm and mm.group(1) != "128":
            w = int(mm.group(1))
        if signed:
            return -(1 << (w - 1)), (1 << (w - 1)) - 1, w
        return 0, (1 << w) - 1, w

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
            if (alg.category or "") in ("cipher", "compression", "decompression"):
                continue
            sig = by_name.get(alg.name)
            if sig is None:
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
            if classify_scalar_shape(sig) is not None and len(alg.inputs or []) == 1:
                harnesses.append(AlgorithmHarness(
                    algorithm=alg.name,
                    category="scalar",
                    rust_call=f"rust_{alg.name}(input)",
                    c_call=f"c_{alg.name}(input)",
                    cases=4000,
                    input_strategy="any::<u64>()",
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
    rng = _rng(_FUZZ_SEED)
    vectors = []
    for data in _gen_byte_inputs(rng, count):
        try:
            out = binding.adapter(fn, bytes(data))
        except Exception:  # noqa: BLE001
            continue
        vectors.append(SpecTestVector(
            description=f"fuzz_input_len_{len(data)}",
            source=f"C reference (scalar): {sig.name}",
            inputs={data_param: _bytes_to_rust_literal(bytes(data))},
            expected_output=str(int(out)),
            tolerance="exact",
        ))
    return vectors


def synthesize_c_vectors(c_source_dir, specs, *, compiler: str = "gcc") -> int:
    """Auto-oracle: for every algorithm with a differentiable shape but NO test vectors,
    mint vectors by running the compiled C reference, and attach them to alg.test_vectors.
    Returns how many algorithms were augmented. This is what lets the fill loop verify
    arbitrary cold C that has no standards KATs -- the C itself is the oracle."""
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
    c_files = sorted(cdir.glob("*.c"))
    if not c_files:
        return 0
    work = cdir / ".alchemist" / "cvec"
    work.mkdir(parents=True, exist_ok=True)
    dll_path = work / ("cref.dll" if _os.name == "nt" else "libcref.so")
    build = build_c_dll(c_files, dll_path, compiler=compiler)
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
            elif classify_digest_shape(sig) is not None:
                vecs = fuzz_digest_vectors(dll, alg, sig)
            elif classify_scalar_shape(sig) is not None:
                vecs = fuzz_scalar_vectors(dll, alg, sig)
            elif classify_inplace_shape(sig) is not None:
                vecs = fuzz_inplace_vectors(dll, alg, sig)
            else:
                vecs = []
            if vecs:
                alg.test_vectors = vecs
                augmented += 1
    return augmented
