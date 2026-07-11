"""Tests for verifier-policed structural decomposition.

The safety guarantee of the whole pass is the offline gcc equivalence gate:
a decomposition is only ever used if it is proven byte-exact against the
original C. These tests exercise that gate on REAL smaz (real codebook, real
codec, real goto) and prove it (a) accepts a genuine helper extraction,
(b) rejects a subtly-broken split, and (c) discriminates correct-vs-broken on
the real function. If gcc is unavailable the gate tests skip.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from alchemist.implementer.structural_decomp import (
    Decomposition, HelperFn,
    parse_decomposition_response,
    verify_c_decomposition_equivalent,
    _classify_shape,
)

FIX = Path(__file__).parent / "fixtures"
_HAS_GCC = shutil.which("gcc") is not None
gcc_only = pytest.mark.skipif(not _HAS_GCC, reason="gcc not on PATH")


# --------------------------------------------------------------------------
# Fixture slicing: pull the codebook preamble + the two fn sources out of the
# vendored real smaz.c (antirez/smaz, BSD).
# --------------------------------------------------------------------------

def _smaz_parts():
    src = (FIX / "smaz.c").read_text(encoding="utf-8")
    i = src.index("int smaz_compress(")
    preamble = src[:i]                       # #includes + both codebooks
    # smaz_compress spans from i to the start of smaz_decompress
    j = src.index("int smaz_decompress(")
    compress = src[i:j].rstrip()
    decompress = src[j:].rstrip()
    return preamble, compress, decompress


# --------------------------------------------------------------------------
# A genuine, hand-verified decomposition of smaz_compress: lift the codebook
# hash-lookup match-finder into a pure helper `smaz_compress__find` and have
# the driver call it. This mirrors what the model is asked to produce; here it
# is hand-written so the gate has a KNOWN-GOOD split to accept.
# --------------------------------------------------------------------------

_FIND_HELPER = r"""
/* Pure match-finder lifted from the inner lookup loop. Given the remaining
 * input, return the matched substring length j (1..7), write the emitted code
 * byte to *emit; return 0 if no codebook match. Recomputes its own hashes. */
static int smaz_compress__find(const char *in, int inlen, unsigned char *emit) {
    unsigned int h1, h2, h3 = 0;
    int j = 7;
    char *slot;
    h1 = h2 = ((unsigned char)in[0]) << 3;
    if (inlen > 1) h2 += (unsigned char)in[1];
    if (inlen > 2) h3 = h2 ^ (unsigned char)in[2];
    if (j > inlen) j = inlen;
    for (; j > 0; j--) {
        switch (j) {
        case 1: slot = Smaz_cb[h1 % 241]; break;
        case 2: slot = Smaz_cb[h2 % 241]; break;
        default: slot = Smaz_cb[h3 % 241]; break;
        }
        while (slot[0]) {
            if (slot[0] == j && memcmp(slot + 1, in, j) == 0) {
                *emit = (unsigned char)slot[slot[0] + 1];
                return j;
            } else {
                slot += slot[0] + 2;
            }
        }
    }
    return 0;
}
""".strip()

_DRIVER_GOOD = r"""
int smaz_compress(char *in, int inlen, char *out, int outlen) {
    int verblen = 0, _outlen = outlen;
    char verb[256], *_out = out;

    while (inlen) {
        int needed;
        char *flush = NULL;
        unsigned char emit;
        int j = smaz_compress__find(in, inlen, &emit);

        if (j > 0) {
            if (verblen) {
                needed = (verblen == 1) ? 2 : 2 + verblen;
                flush = out;
                out += needed;
                outlen -= needed;
            }
            if (outlen <= 0) return _outlen + 1;
            out[0] = (char)emit;
            out++;
            outlen--;
            inlen -= j;
            in += j;
        } else {
            verb[verblen] = in[0];
            verblen++;
            inlen--;
            in++;
        }

        if (!flush && (verblen == 256 || (verblen > 0 && inlen == 0))) {
            needed = (verblen == 1) ? 2 : 2 + verblen;
            flush = out;
            out += needed;
            outlen -= needed;
            if (outlen < 0) return _outlen + 1;
        }
        if (flush) {
            if (verblen == 1) {
                flush[0] = (signed char)254;
                flush[1] = verb[0];
            } else {
                flush[0] = (signed char)255;
                flush[1] = (signed char)(verblen - 1);
                memcpy(flush + 2, verb, verblen);
            }
            flush = NULL;
            verblen = 0;
        }
    }
    return out - _out;
}
""".strip()

# Broken driver: off-by-one on the verbatim flush marker (255 -> 250). Compiles
# fine, diverges on any input that produces a verbatim run.
_DRIVER_BROKEN = _DRIVER_GOOD.replace("(signed char)255", "(signed char)250")


def _preamble_for_gate(preamble: str) -> str:
    # The helper + driver reference memcmp/memcpy and the codebook globals.
    return "#include <string.h>\n" + preamble


# --------------------------------------------------------------------------
# Parsing (no gcc needed)
# --------------------------------------------------------------------------

def test_parse_decomposition_response_json_fence():
    text = '''```json
{"helpers": [{"name": "f__find", "signature": "int f__find(const char*,int)",
  "source": "int f__find(const char *p,int n){return n;}"}],
  "driver": "int f(char*a,int b,char*c,int d){return f__find(a,b);}",
  "rationale": ["lift match"]}
```'''
    deco = parse_decomposition_response(text, "f")
    assert deco is not None
    assert deco.original_name == "f"
    assert len(deco.helpers) == 1
    assert deco.helpers[0].name == "f__find"
    assert "f__find(a,b)" in deco.driver_source
    assert deco.rationale == ["lift match"]


def test_parse_decomposition_rejects_missing_driver():
    assert parse_decomposition_response('{"helpers": [], "driver": ""}', "f") is None
    assert parse_decomposition_response("not json", "f") is None
    assert parse_decomposition_response("", "f") is None


def test_classify_shape_tags_buf_transform():
    # smaz-style codec signature is Tier-1 (independently oracle-able)
    assert _classify_shape("int enc(char *in, int inlen, char *out, int outlen)") \
        == "buf_transform"
    # a scalar helper that returns int from a byte ptr is not a codec shape
    assert _classify_shape("int helper(const char *p, int n)") in (None, "checksum",
                                                                    "buf_transform")


# --------------------------------------------------------------------------
# The equivalence gate on REAL smaz (needs gcc)
# --------------------------------------------------------------------------

@gcc_only
def test_gate_accepts_identity_decomposition_real_smaz():
    """Sanity: the original function as its own 'driver' (no helpers) must be
    proven equivalent. Exercises compiling the real codebook + fuzzing the real
    codec end-to-end."""
    preamble, compress, _ = _smaz_parts()
    deco = Decomposition(original_name="smaz_compress", helpers=[],
                         driver_source=compress)
    ok, report = verify_c_decomposition_equivalent(
        original_c=compress, decomposition=deco, fn_name="smaz_compress",
        shape="buf_transform", preamble=_preamble_for_gate(preamble), n=300,
    )
    assert ok, report
    assert "byte-exact" in report


@gcc_only
def test_gate_accepts_genuine_helper_split_real_smaz():
    """The hand-written match-finder extraction must be proven byte-exact
    against the original smaz_compress over fuzzed inputs."""
    preamble, compress, _ = _smaz_parts()
    deco = Decomposition(
        original_name="smaz_compress",
        helpers=[HelperFn(name="smaz_compress__find",
                          signature="static int smaz_compress__find(const char*,int,unsigned char*)",
                          source=_FIND_HELPER)],
        driver_source=_DRIVER_GOOD,
    )
    ok, report = verify_c_decomposition_equivalent(
        original_c=compress, decomposition=deco, fn_name="smaz_compress",
        shape="buf_transform", preamble=_preamble_for_gate(preamble), n=500,
    )
    assert ok, report


@gcc_only
def test_gate_rejects_broken_split_real_smaz():
    """A subtly-broken split (wrong flush marker) compiles but diverges — the
    gate MUST catch it. This is the fail-closed guarantee."""
    preamble, compress, _ = _smaz_parts()
    deco = Decomposition(
        original_name="smaz_compress",
        helpers=[HelperFn(name="smaz_compress__find",
                          signature="static int smaz_compress__find(const char*,int,unsigned char*)",
                          source=_FIND_HELPER)],
        driver_source=_DRIVER_BROKEN,
    )
    ok, report = verify_c_decomposition_equivalent(
        original_c=compress, decomposition=deco, fn_name="smaz_compress",
        shape="buf_transform", preamble=_preamble_for_gate(preamble), n=500,
    )
    assert not ok
    assert "DIVERGENCE" in report


@gcc_only
def test_gate_declines_unsupported_shape():
    ok, report = verify_c_decomposition_equivalent(
        original_c="int f(void){return 0;}",
        decomposition=Decomposition(original_name="f", driver_source="int f(void){return 0;}"),
        fn_name="f", shape="mystery_shape", preamble="", n=10,
    )
    assert not ok
    assert "no fuzzer" in report


# ---------------------------------------------------------------------------
# Wiring into the TDD fill-loop escalation (P1a): the sound fail-closed hooks.
# These do NOT invoke a model — they prove the guards the escalation relies on.
# ---------------------------------------------------------------------------

class _ExplodingLLM:
    """An LLM stand-in that fails the test if the model is ever called.
    Used to prove the shape gate short-circuits before any model call."""
    def call_structured(self, *a, **k):  # noqa: D401
        raise AssertionError("model must NOT be called on the fail-closed path")


def test_c_function_and_preamble_extracts_fn_and_preamble(tmp_path):
    from alchemist.implementer.tdd_generator import TDDGenerator
    from alchemist.extractor.schemas import AlgorithmSpec

    src = tmp_path / "codec.c"
    src.write_text(
        "#include <string.h>\n"
        "static const int TABLE[3] = {1, 2, 3};\n"
        "int codec_encode(const char *in, int n, char *out, int cap) {\n"
        "    int k = 0;\n"
        "    for (int i = 0; i < n && k < cap; i++) out[k++] = in[i] ^ TABLE[i % 3];\n"
        "    return k;\n"
        "}\n",
        encoding="utf-8",
    )
    gen = TDDGenerator(llm=_ExplodingLLM())
    alg = AlgorithmSpec(
        name="codec_encode", display_name="codec_encode", category="filter",
        description="xor codec", source_files=["codec.c"],
        source_functions=["codec_encode"],
    )
    loc = gen._c_function_and_preamble(alg, tmp_path)
    assert loc is not None
    fn_text, preamble, include_dirs = loc
    # The full function definition is returned...
    assert "codec_encode(const char *in" in fn_text
    assert "return k;" in fn_text
    # ...and the preamble carries the file's globals/#includes but NOT the fn body.
    assert "#include <string.h>" in preamble
    assert "TABLE[3]" in preamble
    assert "return k;" not in preamble
    assert any(p == tmp_path for p in include_dirs)


def test_escalation_fail_closed_on_non_buf_transform_shape(tmp_path):
    """A checksum-shaped function is NOT buf_transform, so the escalation must
    return False WITHOUT calling the model (the equivalence gate can't fuzz it)."""
    from alchemist.implementer.tdd_generator import TDDGenerator
    from alchemist.extractor.schemas import AlgorithmSpec, ModuleSpec
    from alchemist.architect.schemas import CrateSpec

    src = tmp_path / "sum.c"
    src.write_text(
        "unsigned crc_like(unsigned seed, const char *buf, int n) {\n"
        "    unsigned h = seed;\n"
        "    for (int i = 0; i < n; i++) h = h * 31u + (unsigned char)buf[i];\n"
        "    return h;\n"
        "}\n",
        encoding="utf-8",
    )
    gen = TDDGenerator(llm=_ExplodingLLM())
    alg = AlgorithmSpec(
        name="crc_like", display_name="crc_like", category="checksum",
        description="rolling hash", source_files=["sum.c"],
        source_functions=["crc_like"],
    )
    module = ModuleSpec(
        name="sum", display_name="sum", description="", algorithms=[alg])
    crate = CrateSpec(name="sumcrate", description="", modules=["sum"])
    gen._source_root = tmp_path
    # No model call happens: _ExplodingLLM.call_structured would raise. The
    # shape gate returns False first.
    result = gen._attempt_structural_decomposition(
        alg, module, crate, tmp_path / "nonexistent.rs", tmp_path, tmp_path,
        "crc_like",
    )
    assert result is False
