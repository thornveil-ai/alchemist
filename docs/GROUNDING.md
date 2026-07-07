# Alchemist — Grounding & Reconciliation (READ THIS FIRST)

> Written 2026-07-06 after a full-repo audit. Purpose: prevent re-discovering, the
> hard way, that **two parallel translation pipelines exist in this repo** and that
> most of `alchemist/autonomy/` duplicates the mature shipping pipeline. If you are
> an agent resuming work here, read this before writing any new code.

## The two pipelines

**1. The shipping pipeline (the real product).** Entry point `alchemist.cli:app`
(`pyproject.toml` `[project.scripts]`). A mature, spec-first, 6-stage / 6-gate flow,
all checkpointed under `<source>/.alchemist/`:

```
analyze (analyzer/, tree-sitter)  →  extract (extractor/, LLM AlgorithmSpec + standards)
  →  architect (architect/, type_unifier + crate design)  →  implement (implementer/, TDD)
  →  verify (verifier/, 5 fail-closed gates + differential oracle)  →  report (reporter/)
```
It is **already algorithmic**: `extract` produces an `AlgorithmSpec` (math, invariants,
referenced FIPS/RFC standards, test vectors) and *implements from the spec, not the C*;
`verify` checks against **both** the standards KATs **and** the compiled-C differential.
`PRODUCTION_READINESS.md` is the honest status doc (research prototype; ~30–50% on
stateful libs; 127 open zlib debt items).

**2. `alchemist/autonomy/` (an orphaned parallel track).** The shipping CLI imports
**zero** symbols from `autonomy/`. Its own driver is `autonomy/pipeline.py::translate_
project`, reachable only via `python -m alchemist.autonomy.report`. It was built as an
"M1 push-button / zero-per-subject-config" research track but drifted into a *weaker
re-implementation* of the shipping pipeline, and toward pure byte-exact-copy-the-C
(the opposite of the spec-first design). **Do not grow it further as a shadow pipeline.**

## Duplication map (autonomy reinvented these — prefer the shipping module)

| Concern | Shipping (mature — USE THIS) | autonomy/ (retire) |
|---|---|---|
| C parsing | `analyzer/parser.py` (tree-sitter) | `onboard.py`, `c_struct.py` (regex) |
| Type mapping | `architect/type_unifier.py` (workspace coherence) | `type_model.py`, `type_infer.py` |
| KAT / standards | `standards/` + `verifier/test_generator` | `spec_verify.py` (KAT part) |
| Property / roundtrip | `verifier/proptest_gen.py` | `spec_verify.py` (property part) |
| Coverage amplification | `verifier/amplifier.py` (100K + fold-back) | `coverage.py` |
| Multi-sample fill | `implementer/multi_sample.py` | `fill_quality.py::best_of_n` |
| Decomposition | `implementer/decomposed.py` | `decompose.py` |
| Mechanical fixes | `implementer/scrubber.py` (30 rules) | `mechanical.py`, `borrow_fix.py`, `type_fix.py` |
| No-unsafe / safety | `implementer/unsafe_fence.py` + verifier gate | `provenance.py::safety_audit` |
| Receipts | `verifier/receipt.py` (richer, HMAC) | `provenance.py` receipt |
| FFI | `verifier/auto_ffi.py` | `ffi_migrate.py` |
| C→safe-Rust transliteration | `implementer/reference_probe.py` | `safeify.py` (c2rust framing) |
| Global-state → Rust | `architect/global_state.py` (const/LazyLock/Arc<Mutex>) | `effect_oracle.py` + `concurrency.py` |
| Effect footprint oracle | `verifier/adapter_gen.py` (status + bytes) | `effect_oracle.py` |
| Auto differential config | `verifier/auto_config.py` (scalar subjects) | `oracle_gen.py` |
| Orchestration / CLI / packaging | `cli.py`, `pipeline.py` | `pipeline.py`, `report.py`, `program_translate.py`, `packaging.py` |

## Salvage list — genuinely NEW, confirmed absent from shipping (PROMOTE these)

Grep-confirmed **zero** occurrences in shipping code:

1. **Miri memory-safety gate** — no `miri` anywhere in shipping. Promote a Miri gate
   into `verifier/differential_tester` (prove UB-free, complements no-unsafe).
   *(Heap ownership inference malloc→Vec/Box partially overlaps `architect/global_state`,
   which handles GLOBAL state; heap-return ownership may still add value — evaluate.)*
2. **Sanitizer-diff + divergence verdict** — no `-fsanitize`/ASan/UBSan in shipping.
   Promote into `verifier`: on a differential mismatch, run the C under ASan+UBSan; if
   it exhibits UB, verdict = `c-buggy` (the Rust is allowed to differ / is correct).
   Upgrades the differential gate from "must match C" to "match C, or prove C is buggy."
3. **Performance parity** — no benchmarking in shipping. Promote into `reporter/metrics`
   (bench Rust vs C, record ratio) or as a soft gate.
4. **`shim_synth` — auto-synthesized stateful shim** — `extractor/c_shim_fuzz.py` expects
   a HAND-WRITTEN `shim_reset/set/get/run_<fn>` per subject. `autonomy/shim_synth.py`
   generates it from struct fields. This is the real "reduce autonomy debt" advance —
   promote into `extractor`/`verifier` to kill the hand-shim requirement.

Small maybes (evaluate, low priority): pthread→`thread::spawn` mapping in `concurrency.py`
beyond what `architect/global_state` covers; global-state footprint if `adapter_gen`
doesn't capture globals.

## Reconciliation plan

1. **Promote the 4 salvage items** into the shipping pipeline (additive, safe).
2. **Retire the duplicates** — move `autonomy/` duplicative modules to `attic/` (or
   delete) once their unique bits are salvaged. Keep only salvage code, re-homed.
3. **Fix doc credibility**: true test count is **909 collected** (docs say 744 / 201 /
   543 — all stale). `README.md` badge + line 419 + `ROADMAP.md:63` need one true number.
   PyPI `thornveil-alchemist` is a 404 (not published) — docs imply otherwise.
4. **Then** point all effort at the shipping pipeline's real debt (127 zlib items,
   stateful-lib rate, WS3 goto/state-machine structuring, WS5 build detection).

## One-line summary
The product is `cli.py`'s 6-stage spec-first differential pipeline. `autonomy/` is a
parallel weaker re-implementation with **four genuine additions** (Miri, sanitizer-diff,
perf, auto-stateful-shim). Salvage those four, retire the rest, harden the shipping path.
