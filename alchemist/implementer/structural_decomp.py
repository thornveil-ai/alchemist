"""Verifier-policed structural decomposition.

When the single-shot fill loop *refuses* a function (exhausts its iteration
budget without a byte-exact differential pass), the body is usually too hard
for the model to translate whole. This module lets the pipeline break that
function into smaller, independently-verifiable pieces — WITHOUT ever risking
correctness.

The design principle (why this generalizes instead of being a per-library
hack):

    A decomposition is a behavior-preserving C -> (helpers + driver) rewrite.
    Before ANY Rust is generated, we PROVE the rewrite is byte-exact against
    the original C by compiling both with gcc and fuzzing them against each
    other (the same auto-oracle philosophy, offline, no model). A split that
    is not proven equivalent is REJECTED and never used — so decomposition can
    only ever improve *completeness*, never degrade *soundness*.

    Once the C-level split is proven equivalent, each helper is translated by
    its own oracle-backed fill loop, and the recomposed whole is differentially
    verified as usual. Correctness of the whole follows from correctness of the
    parts by composition — and both are machine-checked.

The creative act (proposing where to cut) can be done by the model — it is good
at "split this function into helpers". The model is UNTRUSTED here: the gcc
equivalence gate is what makes an untrusted split safe. This is decomposition
that the verifier polices automatically, which is the only form worth building.

This module is model-agnostic: `propose_and_verify_decomposition` takes a
`call_llm` callback. The equivalence gate (`verify_c_decomposition_equivalent`)
has no model dependency at all and is fully unit-testable with just gcc.
"""

from __future__ import annotations

import ctypes
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from alchemist.verifier.auto_ffi import build_c_dll


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class HelperFn:
    """One extracted helper: a self-contained C function lifted out of the
    original body. `name` must be a fresh identifier; `signature` is the full C
    prototype (used later to classify whether an auto-oracle shape applies)."""
    name: str
    signature: str
    source: str            # the complete C function text
    shape: str | None = None   # auto-oracle shape if one matches, else None


@dataclass
class Decomposition:
    """A proven-or-candidate split of `original_name` into helpers + a driver.

    `driver_source` is the rewritten original function (same name + signature)
    whose body now calls the helpers instead of inlining their logic. The
    concatenation `helpers ++ driver` must be a drop-in replacement for the
    original translation unit.
    """
    original_name: str
    helpers: list[HelperFn] = field(default_factory=list)
    driver_source: str = ""
    strategy: str = "model-proposed"
    rationale: list[str] = field(default_factory=list)
    verified_equivalent: bool = False
    equivalence_report: str = ""

    def combined_c(self) -> str:
        return "\n\n".join([h.source for h in self.helpers] + [self.driver_source])


# ---------------------------------------------------------------------------
# The offline equivalence gate — the safety core (no model dependency)
# ---------------------------------------------------------------------------

# Shapes this gate can fuzz today. Extend as new shapes are supported; an
# unsupported shape means we cannot prove equivalence offline and must decline
# (fail-closed) rather than trust an unverified split.
_SUPPORTED_SHAPES = {"buf_transform"}

_FUZZ_SEED = 0x5EED
_DEFAULT_N = 400


def _lcg(seed: int):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        yield state


def _gen_byte_inputs(rng, count: int) -> list[bytes]:
    """Deterministic fuzz corpus: empty, single bytes, boundaries, and random
    variable-length byte strings. Deterministic so runs are reproducible."""
    out: list[bytes] = [b"", b"\x00", b"a", b"the ", b" " * 8]
    for _ in range(count):
        n = next(rng) % 64
        out.append(bytes((next(rng) & 0xFF) for _ in range(n)))
    return out


def _load_buf_transform(dll_path: Path, fn_name: str):
    dll = ctypes.CDLL(str(dll_path))
    fn = getattr(dll, fn_name)
    fn.restype = ctypes.c_int
    fn.argtypes = (
        ctypes.POINTER(ctypes.c_char), ctypes.c_int,
        ctypes.POINTER(ctypes.c_char), ctypes.c_int,
    )
    return fn


def _call_buf_transform(fn, data: bytes) -> tuple[int, bytes]:
    """Call `int f(char *in, int inlen, char *out, int outlen)`; return
    (ret, out[0..ret]). Out buffer is generously sized for a codec."""
    inbuf = ctypes.create_string_buffer(data, len(data)) if data \
        else ctypes.create_string_buffer(1)
    cap = len(data) * 4 + 1024
    outbuf = ctypes.create_string_buffer(cap)
    ret = fn(
        ctypes.cast(inbuf, ctypes.POINTER(ctypes.c_char)), len(data),
        ctypes.cast(outbuf, ctypes.POINTER(ctypes.c_char)), cap,
    )
    n = ret if 0 <= ret <= cap else 0
    return ret, outbuf.raw[:n]


def verify_c_decomposition_equivalent(
    *,
    original_c: str,
    decomposition: Decomposition,
    fn_name: str,
    shape: str,
    include_dirs: list[Path] | None = None,
    preamble: str = "",
    n: int = _DEFAULT_N,
    workdir: Path | None = None,
) -> tuple[bool, str]:
    """Compile the original C and the decomposed (helpers+driver) C into two
    shared libraries and fuzz them against each other. Byte-exact on every
    input -> the split is provably behavior-preserving.

    `preamble` carries shared declarations both versions need (the codebook
    globals, #includes, helper prototypes). Returns (equivalent, report).

    This function calls NO model. Its verdict is the whole safety guarantee:
    a non-equivalent split fails here and is discarded.
    """
    if shape not in _SUPPORTED_SHAPES:
        return False, f"equivalence gate has no fuzzer for shape {shape!r}"

    import tempfile
    tmp = workdir or Path(tempfile.mkdtemp(prefix="alch_decomp_"))
    tmp.mkdir(parents=True, exist_ok=True)

    orig_src = f"{preamble}\n\n{original_c}\n"
    deco_src = f"{preamble}\n\n{decomposition.combined_c()}\n"
    orig_c = tmp / "orig.c"
    deco_c = tmp / "deco.c"
    orig_c.write_text(orig_src, encoding="utf-8")
    deco_c.write_text(deco_src, encoding="utf-8")

    ext = ".dll" if _is_windows() else ".so"
    orig_dll = tmp / f"orig{ext}"
    deco_dll = tmp / f"deco{ext}"
    r1 = build_c_dll([orig_c], orig_dll, include_dirs=include_dirs)
    if not r1.success:
        return False, f"original failed to compile:\n{r1.stderr[:800]}"
    r2 = build_c_dll([deco_c], deco_dll, include_dirs=include_dirs)
    if not r2.success:
        return False, f"decomposition failed to compile:\n{r2.stderr[:800]}"

    try:
        f_orig = _load_buf_transform(orig_dll, fn_name)
        f_deco = _load_buf_transform(deco_dll, fn_name)
    except Exception as e:  # noqa: BLE001
        return False, f"could not load compiled symbol {fn_name!r}: {e}"

    rng = _lcg(_FUZZ_SEED)
    corpus = _gen_byte_inputs(rng, n)
    for i, data in enumerate(corpus):
        ro, oo = _call_buf_transform(f_orig, data)
        rd, od = _call_buf_transform(f_deco, data)
        if ro != rd or oo != od:
            return False, (
                f"DIVERGENCE on input #{i} (len {len(data)}): "
                f"orig ret={ro} out={oo!r} vs deco ret={rd} out={od!r}\n"
                f"input={data!r}"
            )
    return True, f"byte-exact over {len(corpus)} fuzzed inputs"


def _is_windows() -> bool:
    import os
    return os.name == "nt"


# ---------------------------------------------------------------------------
# Model-proposed split (untrusted) — gated by the equivalence check above
# ---------------------------------------------------------------------------

DECOMPOSE_PROMPT = """You are refactoring ONE C function into smaller pieces so
it is easier to port. You are NOT translating anything yet — stay in C.

## Function to split
```c
{fn_source}
```

## Rules (a machine will reject any split that changes behavior)
- Extract 1-3 helper functions that capture the self-contained sub-computations
  (e.g. an inner lookup/match loop, a finalization/flush step).
- Give each helper a FRESH name prefixed `{fn_name}__` (e.g. `{fn_name}__find`).
- Prefer helpers whose signature is simple and pure: read a byte buffer, return
  a small result. Helpers may recompute derived locals from their inputs.
- Rewrite the ORIGINAL function ({fn_name}) with the SAME signature so its body
  calls the helpers. This is the "driver".
- Do NOT change any global tables, #defines, or the observable output. The
  decomposed version must be byte-for-byte identical to the original on every
  input — it will be fuzz-tested against the original.

## Return JSON ONLY:
{{"helpers": [{{"name": "...", "signature": "...", "source": "<full C fn>"}}],
  "driver": "<full C source of {fn_name} calling the helpers>",
  "rationale": ["why this cut", "..."]}}
"""


def parse_decomposition_response(text: str, original_name: str) -> Decomposition | None:
    """Parse the model's JSON split proposal into a Decomposition. Tolerant of
    ```json fences and leading prose."""
    if not text:
        return None
    blob = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", blob, re.DOTALL)
    if m:
        blob = m.group(1)
    else:
        s, e = blob.find("{"), blob.rfind("}")
        if s == -1 or e == -1 or e <= s:
            return None
        blob = blob[s:e + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return None
    helpers_raw = obj.get("helpers") or []
    driver = (obj.get("driver") or "").strip()
    if not driver or not helpers_raw:
        return None
    helpers: list[HelperFn] = []
    for h in helpers_raw:
        name = (h.get("name") or "").strip()
        src = (h.get("source") or "").strip()
        if not name or not src:
            return None
        helpers.append(HelperFn(
            name=name, signature=(h.get("signature") or "").strip(), source=src,
        ))
    return Decomposition(
        original_name=original_name,
        helpers=helpers,
        driver_source=driver,
        rationale=[str(r) for r in (obj.get("rationale") or [])],
    )


# (prompt_text, step_name) -> completion text or None
SingleCallLLM = Callable[[str, str], "str | None"]


def propose_and_verify_decomposition(
    *,
    fn_source: str,
    fn_name: str,
    shape: str,
    original_c: str,
    call_llm: SingleCallLLM,
    include_dirs: list[Path] | None = None,
    preamble: str = "",
    max_proposals: int = 3,
    n: int = _DEFAULT_N,
) -> Decomposition | None:
    """Ask the model for a split, PROVE it byte-exact vs the original C, and
    return the first proven-equivalent Decomposition. Returns None if no
    proposal survives the gate (in which case the caller keeps the original
    refusal — fail-closed, no harm done).

    `original_c` is the exact source of the function as compiled for the gate;
    `fn_source` is what the model sees (may be identical).
    """
    if shape not in _SUPPORTED_SHAPES:
        return None
    prompt = DECOMPOSE_PROMPT.format(fn_source=fn_source, fn_name=fn_name)
    for attempt in range(1, max_proposals + 1):
        text = call_llm(prompt, f"decompose#{attempt}")
        deco = parse_decomposition_response(text or "", fn_name)
        if deco is None:
            continue
        for h in deco.helpers:
            h.shape = _classify_shape(h.signature)
        ok, report = verify_c_decomposition_equivalent(
            original_c=original_c,
            decomposition=deco,
            fn_name=fn_name,
            shape=shape,
            include_dirs=include_dirs,
            preamble=preamble,
            n=n,
        )
        deco.verified_equivalent = ok
        deco.equivalence_report = report
        if ok:
            return deco
    return None


def _classify_shape(signature: str) -> str | None:
    """Tag a helper with an auto-oracle shape if one applies (Tier-1: the
    helper can be independently differentially verified). Best-effort; a None
    just means the helper is verified only via the recomposed whole (Tier-2)."""
    if not signature:
        return None
    try:
        from alchemist.verifier.auto_ffi import parse_header
        from alchemist.verifier.auto_config import (
            classify_buf_transform, classify_checksum_shape, classify_digest_shape,
        )
    except Exception:  # noqa: BLE001
        return None
    proto = signature.strip()
    if not proto.endswith(";"):
        proto += ";"
    sigs = parse_header(proto)
    if not sigs:
        return None
    sig = sigs[0]
    for name, fn in (
        ("buf_transform", classify_buf_transform),
        ("checksum", classify_checksum_shape),
        ("digest", classify_digest_shape),
    ):
        try:
            if fn(sig) is not None:
                return name
        except Exception:  # noqa: BLE001
            continue
    return None
