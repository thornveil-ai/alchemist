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

## Reconciliation — ✅ COMPLETE (2026-07-06)

1. **Promoted the 4 salvage items** into the shipping pipeline:
   - **Miri gate** → `verifier/differential_tester.py` (optional 7th gate, `verify --miri`).
   - **sanitizer-diff + divergence** → `verifier/sanitizer_diff.py` (`sanitizer_check`,
     `divergence_verdict` → "match C, or prove C is buggy").
   - **perf parity** → `reporter/perf.py` (`bench_scalar`, ratio → parity/faster/regressed).
   - **shim_synth** → `extractor/shim_synth.py` (auto-synthesize the mechanical stateful
     shim accessors; self-contained struct parser inlined).
2. **Retired `alchemist/autonomy/` entirely** — the whole package (~6.3k LOC) + its
   ~30 duplicate test files deleted. Confirmed **zero** shipping code imported it, so
   deletion was safe. Test suite: **693 passing / 7 skipped** (was 901 with the
   autonomy tests). The 11 orphaned-track docs live in `docs/archive/`.
3. **Doc credibility fixed** — true count corrected everywhere; PyPI-404 and the
   orphaned-track overstatement corrected in README/ROADMAP/PRODUCTION_READINESS.

### Follow-up wiring (small, optional)
- Record `perf_ratio` in the shipping `verifier/receipt.py` (perf module is promoted;
  it isn't yet threaded into the receipt).
- Wire `shim_synth` into `extractor/c_shim_fuzz.py` so auto-generated accessors replace
  hand-written ones per subject (module promoted; not yet called by the pipeline).

## One-line summary
The product is `cli.py`'s 6-stage spec-first differential pipeline. The orphaned
`autonomy/` track has been **retired**; its four genuine additions (Miri, sanitizer-diff,
perf, shim_synth) were **promoted** into shipping. The repo is now single-pipeline and
clean. Next: the shipping pipeline's real debt (127 zlib items, stateful-lib rate, WS3
goto/state-machine structuring, WS5 build detection).
