# Alchemist — Grounding & Reconciliation (READ THIS FIRST)

> Written 2026-07-06 after a full-repo audit. Purpose: prevent re-discovering, the
> hard way, that **two parallel translation pipelines exist in this repo** and that
> most of `alchemist/autonomy/` duplicates the mature shipping pipeline. If you are
> an agent resuming work here, read this before writing any new code.

## ⚠️ ADDENDUM 2026-07-11 — full-repo re-audit + the ONE rule that was broken

**THE ONE RULE: Alchemist IS the converter. The MODEL (Gemma via vLLM) writes every
line of Rust; you build/run/verify/sharpen the converter. You NEVER hand-write the
translation output.** In this session an agent drifted into hand-writing a Rust Lua
interpreter (`artifacts/lua-rs/`, since removed) — the exact "shadow pipeline / copy-
the-C-by-hand" anti-pattern this doc forbids, made worse because `architect/
type_unifier.py` + `workspace_assembler.py` are *designed to produce the shared type
universe automatically* from model output. If you catch yourself writing `.rs` that
isn't a pipeline template/test, STOP — you are doing the machine's job.

**True state (every file read 2026-07-11):**
- **Verified in-repo:** `subjects/tinychk` (PASS) and `subjects/zlib` **`zlib-checksum` only**
  (adler32+crc32, 5000 cases, byte-exact). zlib deflate/inflate in the live output are
  `unimplemented!()` stubs, honestly excluded from the receipt. `references/*_verified`
  (base64, ArduPilot CRC, zlib-trees partial, inflate_table) are real, `unsafe`-free,
  oracle-backed. **`subjects/lua` = analysis + oracle ONLY — zero generated Rust.**
- **Honest maturity:** ~30–50% of functions on *stateful* libs; kernel/OS near-zero
  (see PRODUCTION_READINESS.md). A whole cyclic interpreter core is beyond current reach.
- **The fail-closed contract is real AND tested** (missing oracle→differential FAILS
  "REFUSING"; unverifiable category→`panic!`; nothing stubbed is reported verified).

**Was: the repo's best code is DEAD (built + tested + UNWIRED).** ✅ RESOLVED 2026-07-11:
- `implementer/structural_decomp.py` — **WIRED** (P1a, commit a6108a6) into the TDD
  refusal escalation: a refused buf_transform fn now gets a gcc-PROVEN byte-exact
  C split, then a piecewise translation re-verified by the same differential test.
  Fail-closed (unproven split discarded, failed translation reverts).
- `verifier/e2e_oracle.py` — **WIRED** (P1b, commit 72bdbb4) as `DifferentialConfig.
  e2e_spec` + `DifferentialTester.gate_e2e`: whole-program observable-behavior
  differential for cyclic cores (Lua/PX4). Folded into `report.passed` + receipt;
  fails closed on divergence / empty corpus / crash; not-run PASS when no spec.
- Still UNWIRED (candidate future work, not dead-delete): `verifier/{sanitizer_diff,
  amplifier}.py`, `implementer/{decomposed,parallel,regression}.py`, `analyzer/
  preprocessor.py`, `function_classifier.py` (real build-utility filter), `shim_synth.py`.
  Removed the truly-dead code (`_extract_module_OLD_BULK`, `_ZLIB_INFLATE_SHIM_BINDINGS_
  PENDING`) in commit 6c5390d.

**Generalization bottleneck — partially closed.** `type_unifier` **auto-populates**
canonicals from analysis.json now (P2, commit 822c4eb): struct fractures with
structurally-compatible spellings unify without hand-registration; curated registry
still overrides for the semantically-hard cases (ct_data union-flattening). Still
zlib-populated: `normalizer`, `spec_auditor`, `field_scanner.TYPE_HINTS`,
`module_detector` filename sets, `state_mutator`/`c_shim_fuzz` bindings.

**Debt — PAID (commits 6c5390d, 145da2b):** brace scanners consolidated onto the
token-aware `scrubber.find_matching_brace` (constants_extractor already delegated;
struct_lift now routes through it); the two `_snake` renamed to signal their
deliberate divergence (`skeleton._snake` preserves boundary underscores,
`api_completeness._snake_loose` strips them); the 3 dead-logic bugs fixed
(`validator._check_orphan_rule`, `auto_config.py:1426`, `trait_extractor._normalize_type`).
**CI STILL runs only Python unit tests + anti-stub self-scan — it does NOT run the
pipeline, invoke a model, or build generated Rust. Green CI ≠ a working converter.**

**On-mission plan:** (1) wire `structural_decomp` + `e2e_oracle` ✅; (2) auto-populate
`type_unifier` ✅; (3) pay down the debt ✅; (4) run the converter to validate —
IN PROGRESS; THEN (5) Lua the right way — the *model* translates leaf-up, gated by the
differential + `e2e_oracle`, refusal-rate the metric. Never hand-write.

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
| No-unsafe / safety | skeleton emits `#![forbid(unsafe_code)]` (compiler-enforced) + `verifier/differential_tester.py::gate_no_unsafe` | `provenance.py::safety_audit` |
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
clean.

**Note on "debt":** the "127 zlib items / WS3 / WS5" numbers that appear in older docs
were the RETIRED autonomy track's *automation debt* — the count of human-supplied
artifacts (oracle shims, build configs, review confirmations) the push-button engine
wanted to auto-synthesize. They are NOT unsolved zlib bugs. zlib is translated
byte-exact today (deflate+inflate round-trip, 21/21 — see zlib_case_study.md). With
the autonomy track retired, that automation-debt ledger is retired with it.

**zlib surface completed 2026-07-07:** the zlib workspace on the RigRun box now has
**zero `unimplemented!()`, 454 tests green, byte-exact vs C at levels 0–9.** All 18
previously-stubbed functions were resolved: 16 implemented + differentially verified
(notably `deflate_stored`/level-0 byte-exact across block boundaries, and all 7
compress/uncompress wrappers), and 2 documented safe-port omissions (`inflate_fast` =
unsafe-pointer optimization with no safe equivalent; `inflate_back` = broken-placeholder
signature, zero callers). A test-gen bug was also found+fixed (20 `compress_bound` KATs
disagreed with real C). Durable snapshot:
`subjects/zlib/.alchemist/zlib_complete_verified_2026-07-07.tar.gz` on the box.
The remaining real frontier: gzip wrapper (`wbits +16`), incremental multi-call
streaming, and broadening proven coverage beyond the current subjects.
