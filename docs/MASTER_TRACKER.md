# Alchemist — Master Tracker

**Autonomous C/C++ → verified safe Rust, on a local model (Gemma 4 31B, US-origin).**

The one document for the whole climb: **~285 concrete milestones** across **8 vertical phases** (integration checkpoints — prove the stack on a bigger target) and **6 capability tracks** (reusable capabilities, built once, applied everywhere). Each item has a definition-of-done and a difficulty tag. Finish every item and the project is genuinely complete: point it at a C/C++ codebase, walk away, come back to verified safe Rust.

> Interactive, checkable version: `docs/master-tracker.html` (progress persists in-browser).

## Progress at a glance  *(as of 2026-07-12)*

| Phase / Track | Done | Status |
|---|---|---|
| **F** · Foundations | **12/12** | ✅ complete |
| **P0** · Reliability Floor | **14/14** | ✅ complete (+P0.8a) |
| **P1** · Whole Small/Mid C Library | **5/16** | 🔨 in progress (1 active) |
| P2 · Scale — Large Single Codebase | 0/12 | ⬜ not started |
| P3 · C++ Frontier | 0/8 | ⬜ |
| P4 · Embedded & Unsafe Boundary | 0/8 | ⬜ |
| P5 · ArduPilot | 0/22 | ⬜ frontier |
| P6 · Autonomy — Point & Walk Away | 0/12 | ⬜ continuous |
| Track · SEM (semantics) | 0/70 | ⬜ * |
| Track · VER (verification) | 0/25 | 🔨 2 active * |
| Track · MODEL | 0/21 | 🔨 1 active * |
| Track · IDIOM | 0/12 | ⬜ * |
| Track · PERF | 0/8 | ⬜ * |
| Track · INFRA | 0/20 | ⬜ * |
| **TOTAL** | **31/260 (12%)** | |

\* **Track vs phase counts overlap and are honest by design.** The 6 capability Tracks are the reusable-capability backlog; when a track capability is *delivered*, it is recorded against the phase item that demanded it (e.g. the struct-carry, type-unifier, e2e-oracle, and decomposition capabilities live as **F.7–F.9** and the shape system as **P0.8/P0.8a/P0.9 + P1.15**), not double-checked in the Track list. So the Track checkboxes read low even though much of their machinery is built and verified — they track *remaining* capability, phases track *delivered* capability. The reliability floor (F+P0 = 26 items) is 100% done; the current front is **P1**.

## Where we sit in the field (researched, not guessed)

- **DARPA TRACTOR (2024)** — a DoD program to translate *all* C to idiomatic, safe Rust. Validates the vision at the national-security level and is a funding lane. Our edge: verification-gated, model-writes-every-line, fail-closed.
- **c2rust (Galois/Immunant)** — the mature mechanical transpiler, but it emits *unsafe*, unidiomatic Rust. Turning that into safe idiomatic Rust is the open problem we attack.
- **Laertes (OOPSLA'21)** — automated unsafe→safe refactoring; its bounded success is the evidence this is genuinely hard.
- **LLM-translation studies** — LLMs translate plausibly but unreliably; correctness demands an oracle. That finding *is* our thesis: the differential gate, not the model, is the source of truth.
- **Verification ladder** — Miri (UB) → Kani (bounded model checking) → Prusti/Creusot/Verus (deductive) → Aeneas (functional translation validation). Climbed in the VER track.

**Honest bottom line:** the machinery is built and general. What remains is a ladder of real capability and reliability. "Perfect *safe* Rust for all of ArduPilot" is impossible as literally stated (hardware code is irreducibly unsafe); the real target is verified safe logic + a thin, audited unsafe shim.

## Legend

`eng` engineering · `wire` wire existing-but-dead code · `research` research-hard/open problem · `model` model-dependent · `infra` infrastructure · `product` product/GTM · `unsafe` irreducible unsafe boundary

Status: `[ ]` to-do · `[~]` active · `[x]` done · `[!]` blocked

---

## Architecture — how the machine works, and where every item lives

*Read this once and the whole tracker becomes navigable: each phase/track item below is a change to one of the components described here. Every item's note names the component and commit; this section says what that component IS and where its code lives. Paths are relative to the repo root (`alchemist/…`). Line counts are approximate load-bearing sizes, not limits.*

### 0. The one idea

**The oracle, not the model, is the source of truth.** A local model (Gemma 4 31B, US-origin, on the box at `:8086`) writes every line of Rust. Nothing it writes is trusted until a **byte-exact differential oracle** — the compiled C reference, fuzzed through FFI and compared against the Rust — agrees on every input. **No oracle ⇒ refuse** (fail-closed). We never hand-write translation output; we build, run, and sharpen the *converter*. A refusal is an honest "we can't prove this yet," never a silent stub.

### 1. The 6-stage pipeline  (`pipeline.py` orchestrates; `cli.py translate` is the entry point)

```
   C source dir
       │
  [1] analyze   analyzer/         parse C, build call graph, detect algorithmic modules
       │                          → parser.py, call_graph.py, module_detector.py, preprocessor.py
  [2] extract   extractor/        per-fn spec: signature, Rust-lifted types, test vectors, category
       │                          → spec_extractor.py, normalizer.py, function_classifier.py, schemas.py
  [3] architect architect/        design the crate/trait/type layout across modules
       │                          → crate_designer.py, trait_extractor.py, type_unifier.py, validator.py
  [4] implement implementer/      TDD fill: skeleton → emit tests → model fills each fn → in-loop verify
       │                          → tdd_generator.py (the heart), skeleton.py, test_generator.py
  [5] verify    verifier/         the 5-gate final differential proof (see §3)
       │                          → auto_config.py, adapter_gen.py, proptest_gen.py, differential_tester.py
  [6] report    reporter/         refusal ledger, metrics, perf, signed receipt
                                   → refusal_ledger.py, metrics.py, perf.py; receipt in verifier/receipt.py
```

Specs are checkpointed to `<subject>/.alchemist/specs/`; a run is resumable. `solo.py` runs a scoped single-/few-function translate for fast iteration; `lib_orchestrator.py` runs whole libraries.

### 2. The shape system — the central abstraction (this is what most items touch)

A C function is classified into a **shape** by its signature. The shape determines how the oracle mints inputs, compares outputs, and what tolerance applies. **This is the extensibility surface: adding support for a new kind of function = adding a new shape.**

**Shape catalog** (each is a `classify_*` + `fuzz_*` pair in `verifier/auto_config.py`, plus emitters):

| Shape | C signature (archetype) | Rust lift | Oracle |
|---|---|---|---|
| `checksum` | `u32 f(const u8*, len[, seed])` | `fn(&[u8][,seed])->u32` | scalar compare, fold boundaries |
| `hash`/`digest` | `void f(const u8*, len, u8* out)` | `fn(&[u8])->Vec<u8>` | digest bytes + NIST/FIPS catalog KATs |
| `scalar` | `T f(scalars…)` | `fn(scalars)->T` | scalar compare |
| `inplace` | `void f(u8* buf, len)` | `fn(&mut[u8])` | mutated-buffer compare |
| `buf_transform` | `int f(in,inlen,out,outlen)` | `fn(&[u8])->Vec<u8>` | out[0..ret]; **decoder→roundtrip via `_paired_encoder_name`** |
| `cbuf_out` | `char* f(char*)` (text→text, e.g. NMEA) | `fn(&str)->String` | result-string compare |
| `cstr_out` | `char* f(char*)` (text encoder) | `fn(&[u8]\|&str)->String` | NUL-terminated string compare |
| `cstr_scalar` | `T f(const char* s, scalars…)` | `fn(&str,…)->T` | scalar compare |
| `iarray_reduce` | `T f(const int* a, n)` | `fn(&[int])->T` | scalar reduce |
| `buf_gen` | `u8* f(size n,…)` | `fn(n,…)->Vec<u8>` | generated-buffer compare |
| `cstr_roundtrip` | `char* f(char*)` **binary-out decoder** | `fn(&str)->Result<Vec<u8>,E>` | **P1.15**: mint via paired C encoder, `decode(encode(p))==p` |
| `cipher_seq` / `alloc_seq` / `hash_seq` | init+op sharing a struct | struct-carried | sequence differential (state observer) |
| `scalar_mutator` | `void f(&mut State, scalars)` | struct-carried | state-mutation differential |

**⚠️ The N-site wiring rule (the single most important thing to know when adding/reading a shape).** A shape is not one function — it is wired at **5–7 sites that must all agree**, and there are **TWO independent vector-dispatch paths** that both need the shape or the fill loop silently sees "no test vectors":

1. `classify_<shape>()` + `fuzz_<shape>_vectors()` — `verifier/auto_config.py`
2. **Dispatch A** — `synthesize_c_vectors()` per-fn dispatch — `verifier/auto_config.py` (the pipeline calls this)
3. **Dispatch B** — the `TDDGenerator` fuzz backfill dispatch — `implementer/tdd_generator.py` (~line 2416). The generator **clears machine-tagged vectors and re-mints via its own dispatch**; a shape missing here dies even if Dispatch A produced vectors. *(This bit us on P1.15.)*
4. `build_diff_config()` harness branch — `verifier/auto_config.py` (feeds the final gate; must be checked before more-general shapes)
5. proptest block `_proptest_<shape>_block()` + `VALID_CATEGORIES` — `verifier/proptest_gen.py`
6. FFI adapter branch — `verifier/adapter_gen.py` (emits `rust_<fn>` and `c_<fn>` wrappers)
7. fill-loop test emitter `_emit_<shape>_test()` + the cargo-test name filter in `_test_filters_for_fn()` — `implementer/test_generator.py` + `tdd_generator.py`. *(A missing filter ⇒ 0 tests run ⇒ false "no test vectors". Also bit us on P1.15.)*

Canonical worked example of all 7 sites: **P1.15 `cstr_roundtrip`** (commits 07020fd→c8bff85). Simpler examples: **P0.8a `cstr_out`**, **P0.8 `iarray_reduce`/`cstr_scalar`**, **P1-baseline `buf_gen`**.

### 3. The verification gate stack  (stage 5; the fail-closed proof)

Emitted by `auto_config.build_diff_config()` → `adapter_gen` + `proptest_gen` into a throwaway `verify_gen/` crate, run by `differential_tester.py`:

- **gate 1** `cargo check --workspace` — it compiles.
- **gate 2** anti-stub scan (`implementer/anti_stub.py`) — no `todo!()`/`unimplemented!()`/trivial-constant returns.
- **gate (structural)** no-`unsafe` proof — the output is safe Rust.
- **gate 3** semantic lints (`implementer/semantic_lints.py`) — no oracle-evading shortcuts.
- **gate 4** `cargo test --workspace` — the spec/KAT vectors (C-minted) pass.
- **gate 5** differential proptest — fresh fuzzed inputs, Rust vs C **live**, byte-exact.

**Vector minting & crash isolation** (`synthesize_c_vectors`): the C reference is compiled to a DLL and called via `ctypes`; because fuzzed inputs hit real C undefined behavior, minting runs in a **forked child** — a segfault returns 0 vectors (fail-closed) instead of killing the translator. A signed receipt (`verifier/receipt.py`) seals gates+harnesses+oracle+env with a content-SHA256 (optional HMAC).

### 4. Type & memory model  (how the skeleton compiles cold)

- **struct-carry** (`verifier/struct_lift.py`, wired in `pipeline.py`) lifts C state structs into Rust so the skeleton compiles before any body is filled. Resolves scalar typedefs (`BYTE`→`u8`), enum typedefs (`jsmntype_t`→`i32`), strips `#ifdef` in struct bodies, and raw-escapes keyword fields (`type`→`r#type`).
- **type_unifier** (`architect/type_unifier.py`) auto-derives one coherent type model across fractured modules from the analysis (no hand-written registry — F.9).
- **normalizers** (`extractor/normalizer.py` + `auto_config` lifts) canonicalize specs; **`solo._load_specs_and_arch` re-applies them on every reload** so a reloaded spec matches the in-memory one (P0.3).

### 5. Fill escalation ladder  (`implementer/tdd_generator.py`, cheapest→dearest; `won_via` records which tier won)

`cached` (subject-anchored win cache `<subject>/.alchemist/wins`, P0.4) → deterministic `template` (init/reset `init_templates.py`; static-table no-op; free/destroy no-op) → `single` model fill → `multi_sample` best-of-N (`multi_sample.py`) → `holistic` whole-file fixer (`holistic.py`, self-terminates after 2 no-op patches, P0.5) → `decomposition` gcc-proven byte-exact split (`structural_decomp.py`, F.7). Reference transliteration via `reference_probe.py`.

### 6. Reliability & observability layer

- **refusal ledger** (`reporter/refusal_ledger.py`) — the north-star metric: per-fn verified/refused + reason + `won_via` + telemetry (`elapsed_s`/`llm_calls`/`output_tokens`), plus `wins_by_tier` rollup. Written to `<subject>/.alchemist/refusal_ledger.json`.
- **deterministic replay** — `ALCHEMIST_DETERMINISTIC=1` forces temp 0 + single-sample everywhere (byte-identical output proven, P0.13).
- **benchmarks** — `bench/leaf/` (26 unseen leaf fns → scorecard, P0.11) and `bench/lib/run_libbench.py` (whole-lib batch → per-lib + overall refusal, P1.10). Nightly cron runs the real pipeline+model (P0.12).

### 7. How to trace any tracker item to its code

Every completed item's note carries **(a)** the component/shape it changed (names map to §1–6 above), **(b)** the commit SHA, and **(c)** the box-validation result where model-dependent. To go from an item to code: read the note → find the named module in the map above → `git show <sha>`. New capability items are almost always "a new shape" (§2, the 7 sites) or "a new gate/lever" (§3/§5).

**Component → primary file quick map:**

| Concern | File(s) |
|---|---|
| Pipeline orchestration | `pipeline.py`, `cli.py`, `solo.py`, `lib_orchestrator.py` |
| Analyze | `analyzer/{parser,call_graph,module_detector,preprocessor}.py` |
| Extract / specs | `extractor/{spec_extractor,normalizer,function_classifier,schemas,fuzz_vectors}.py` |
| Architect / types | `architect/{crate_designer,trait_extractor,type_unifier,validator,schemas}.py` |
| **Shapes & oracle config** | **`verifier/auto_config.py`** (classify/fuzz/synthesize/build_diff_config) |
| Fill loop (the heart) | `implementer/tdd_generator.py` |
| Skeleton / tests | `implementer/{skeleton,test_generator,init_templates}.py` |
| Struct-carry | `verifier/struct_lift.py` |
| Gate emit | `verifier/{adapter_gen,proptest_gen,differential_tester,auto_ffi}.py` |
| Gates (stub/lint) | `implementer/{anti_stub,semantic_lints}.py` |
| Escalation tiers | `implementer/{multi_sample,holistic,structural_decomp,reference_probe}.py` |
| Report / receipts | `reporter/{refusal_ledger,metrics,perf}.py`, `verifier/receipt.py` |
| Benchmarks | `bench/leaf/`, `bench/lib/` |

---

## F · Foundations — already in the ground (DONE)

*What exists and is verified today. The platform everything else stands on.*
**Exit:** a general, fail-closed, spec-first pipeline with real verified conversions behind it.

> **Foundations → code** (each F item's primary location; see the Architecture §1 map for the full stage breakdown):
> **F.1** `pipeline.py` + `cli.py` (stages) · **F.2** `verifier/auto_config.py` + `verifier/differential_tester.py` (oracle) · **F.3** zlib workspace under `subjects/zlib*/` + `verifier/zlib_config.py` · **F.4** `subjects/sha256/` + `standards/catalog.py` (CAVP KATs) · **F.5** libcrc subject workspace · **F.6** `implementer/scrubber.py` + `verifier/auto_ffi.py` (static/inline strip + macro neutralize) · **F.7** `implementer/structural_decomp.py` (wired in `implementer/tdd_generator.py`) · **F.8** `verifier/e2e_oracle.py` (gated in `pipeline.py` verify) · **F.9** `architect/type_unifier.py` · **F.10** `implementer/tdd_generator.py` (cargo-fix pass, commit 36f1233) · **F.11** `verifier/auto_config.py` + `implementer/semantic_lints.py` (the three false-refusal fixes) · **F.12** Lua subjects under `subjects/lua*/`.

- [x] **F.1** 6-stage spec-first pipeline — analyze → extract → architect → implement → verify → report, checkpointed, model-in-the-loop `eng`
- [x] **F.2** Fail-closed byte-exact differential oracle — compile C ref, FFI-fuzz vs Rust; no oracle → refuse `eng`
- [x] **F.3** zlib byte-exact — deflate+inflate+checksums, round-trip byte-exact vs C at levels 0–9 `model`
- [x] **F.4** SHA-256 CAVP-green — cold → safe Rust, NIST CAVP wired into the gate `model`
- [x] **F.5** libcrc 9/9 verified workspace — whole lib, zero hand-edits `model`
- [x] **F.6** Static-internal-fn exposure keystone — strip static/inline + neutralize export macros for oracle linkage `eng`
- [x] **F.7** structural_decomp wired into refusal escalation — gcc-proven byte-exact split, fail-closed `eng`
- [x] **F.8** e2e_oracle wired as a fail-closed gate — whole-program observable-behavior differential `eng`
- [x] **F.9** type_unifier auto-derives from analysis — struct-fracture coherence without a hand-written registry `eng`
- [x] **F.10** cargo-fix mechanical-repair lever — apply rustc machine-applicable edits before refusing `eng`
- [x] **F.11** Three verification false-refusals killed — decimal-vs-hex, min(usize,u32), deleted live method `eng`
- [x] **F.12** Lua leaf functions conquered from real source — luaS_hash + luaO_ceillog2 byte-exact `model`

---

## P0 · Reliability Floor (✅ COMPLETE — all 14 items + P0.8a)

*Make single-function C→Rust on Gemma dependable. The wall we hit this week: correct code, sunk by mechanical trivia and false refusals.*
**Exit (all met):** tinychk reliably 4/4 ✅ · unseen leaf fns ≥90% verified (26-subject bench: 24/26 = 92.3%, cold-confirmed) ✅ · refusal ledger live (+ per-fn timing/cost + win-by-tier audit) ✅ · nightly cron runs the real pipeline+model ✅. *Also delivered: deterministic-replay mode (byte-identical proven), subject-anchored win cache, spec-reload normalization, two new oracle shapes (iarray_reduce/cstr_scalar), cstr_out final-gate wiring.*

- [x] **P0.1** Clean single-fn repro harness — `ALCHEMIST_FILL_TRACE=<dir>` dumps model Rust + compile error + differential divergence per iteration `eng` `infra` *(commit 4f49675)*
- [x] **P0.2** Root-cause the tinychk differential fails — **found via the trace**: `test_generator._emit_spec_test` ordered the KAT call by fuzz-vector dict order (`buf, seed`) not the signature (`seed, buf`) → uncompilable test → refused correct code forever. Fixed → **tinychk 4/4 OVERALL PASS** `eng` *(commit a22d18d)*
- [x] **P0.3** Fix verify_gen ↔ spec coupling — **the verify stage (and solo) reloaded specs from disk via `_load_specs_and_arch`, which applied only the generic normalizer, NOT the three auto_config type-lifts the implement stage applies in-memory** (byte-buffer→&[u8], C-`char`-value→i8/u8, digest→`fn(&[u8])->Vec<u8>`). So a reload saw pre-normalization specs → `build_diff_config` disagreed with the model's actual (normalized) signature (the P0.8 E0308). Fixed at the root (commit 78d1b32): `_load_specs_and_arch` now applies the same three (idempotent) normalizers, so every reload is canonical. **Validated on box: count_char (reload path) + crc32b (byte-buffer, no regression) both OVERALL PASS.** +1 reload regression test. `eng`
- [x] **P0.4** Win-cache restore determinism — **done (commit 3703d4f).** The wins cache anchored to `workspace_dir.parent/"wins"`, which for an external `--output` (translate's normal mode; leaf bench uses a `/tmp` tempdir) is the SHARED temp ROOT — so every subject wrote to one `/tmp/wins` keyed only by `crate/module/fn`. Restore was non-deterministic (depended on where `--output` sat), subjects could collide, and it silently made the leaf benchmark **not cold** (prior-run wins short-circuited fills → the reported first-pass was mostly cached restores). Fixed: `_wins_cache_path` anchors to the source root (`subject/.alchemist/wins`) via the `_source_root` the generator already holds, so restore is deterministic regardless of `--output` and `run_leafbench`'s `_clean_state` produces a genuinely cold run. +3 tests. Suite 764. **The truly-cold re-run confirms the benchmark was NOT inflated: 24/26 OVERALL PASS, first-pass 92.3% — identical to the cached numbers, i.e. the model genuinely first-fills these leaf shapes.** `eng`
- [x] **P0.5** Kill holistic-fixer empty-patch no-ops — **done (commit 78bbf9a, `implementer/holistic.py`).** The `HolisticFixer` loop `continue`d on an empty/all-rejected patch and counted a byte-identical rewrite as a "change", so it could grind every iteration with no progress and no diagnosis. Now: `_apply_patch` only counts genuine content changes (compares against on-disk); the loop tracks consecutive no-op iterations and **bails after 2 with a `bail_reason`** instead of burning the budget; the caller (tdd_generator) surfaces the reason and — since the fixer now self-terminates when stuck — is uncapped from `max_iter=1`→3 so a productive multi-step fix (error A → then error B) isn't cut off at one pass. +3 unit tests (empty-patch bail, identical-content no-op, real-fix success). Suite 760. `eng`
- [x] **P0.6** Escalation-ladder audit — **done (commit 09a5d51; `implementer/tdd_generator.py` sets `won_via` at each win site, `reporter/refusal_ledger.py` rolls up `wins_by_tier`).** `FunctionAttempt.won_via` now records which tier PRODUCED each win — `cached | template | single | multi_sample | holistic | decomposition` (or "" if refused), set at every win site in the fill loop. The refusal ledger rolls it up as `wins_by_tier` (verified wins per tier, cheap→expensive) and the pipeline prints it, so over any corpus a tier with zero wins is visibly not earning its budget (dead weight or a rare safety net). The tier thresholds ARE the budgets (`multi_sample_after`/`holistic_after`/`max_iter_per_fn`/`multi_sample_n`, all TDDGenerator ctor knobs). **Validated on box: count_char + sum_array both `wins by tier: single=1` — i.e. the model first-fills leaf shapes and the escalation tiers are pure safety nets there; harder libraries will light up the higher tiers.** +1 test. Suite 765. `eng`
- [x] **P0.7** Refusal-rate instrumentation — every translate run emits `<subject>/.alchemist/refusal_ledger.json` (per-fn verified/refused + reason + escalations) and prints the refusal rate `infra` *(reporter/refusal_ledger.py)*
- [x] **P0.8** Systematic false-refusal sweep — **closed two real gate-coverage gaps (commit 4d26f9f), driven by the benchmark's own planted probes.** Added two common leaf shapes end-to-end (classify + TDD vectors + final-gate harness + proptest + FFI adapter): **iarray_reduce** `<scalar> f(const T* a, int n)` (sum_array/imax_array) and **cstr_scalar** `<scalar> f(const char* s, ...)` (count_char). Two bugs found by RUNNING the converter: (1) a C `char` value-arg mis-lifts to Rust `char` (4-byte) — new `normalize_char_scalar_params` re-lifts to i8/u8 (the byte it is); (2) the verify stage can hold a pre-normalization spec, so `build_diff_config` emitted `any::<char>()` while the wrappers were `i8` → E0308, now coerced `char`→i8. **All three new subjects OVERALL PASS end-to-end on the box.** Corpus grown to 26 with two fresh honest-refusal probes (double scalar, void in-place int array). +11 regression tests. (The broader "audit every one of 257 refusal sites" is deliberately scoped to benchmark-surfaced refusals — probes flush real gaps, speculation doesn't.) `eng`
- [x] **P0.9** No gate may veto a differentially-proven-correct fn — **the P0.11 "verified-function vs green-workspace" gap is FIXED (commit be7897b).** Root cause found by *running the converter* (not the assumed traits-stub): the `char* f(char*)` **cstr_out** shape added in P0.8a was wired into the TDD test vectors but NOT into the three sites the FINAL differential gate uses — `build_diff_config` (→ no harness → config `None` → refuse), `proptest_gen`, `adapter_gen`. Plus a second miss: the extractor labels rot13 "cipher" (it *is* a substitution cipher) and the cipher/compression early-skip dropped it before the cstr_out branch — the semantic label must not starve a shape with a sound differential. Both fixed + 4 regression tests. **Validated end-to-end on the box (Gemma :8086): to_upper / hex_encode / rot13 all FAIL→OVERALL PASS, differential genuinely runs.** (Broader anti-stub-lint false-positive sweep folds into P0.8.) `eng`
- [x] **P0.10** Stale-lock auto-reclamation — **already implemented + tested** (`alchemist/workspace_lock.py` reclaims dead-PID locks; `test_stale_lock_reclaimed`). Session pain was orphaned *live* processes (SSH-timeout leftovers), not a lock bug — an operational issue, not a code one `eng`
- [x] **P0.11** Leaf-function benchmark suite — 23 unseen pure C leaf fns (`bench/leaf/gen_corpus.py` + `run_leafbench.py` → `scorecard.json`). **First result (box, Gemma :8086): verified 21/23 = 91.3% · first-pass 21/23 = 91.3% · refusal 8.7%.** By category: checksum 8/8, scalar 10/10, cstr 3/3, uncovered 0/2 (the 2 planted coverage gaps, honestly refused). **Gap it surfaced (now FIXED in P0.9, commit be7897b): initially 21 verified but only 18/23 OVERALL PASS** — the 3 single-fn cstr subjects verified byte-exact yet the FINAL differential gate refused them (cstr_out shape unwired past the TDD vectors). After the P0.9 fix a fresh cold run is **21/23 OVERALL PASS** (checksum 8/8, scalar 10/10, cstr 3/3, uncovered 0/2). Also fixed a metric bug in the runner: first-pass used `(iters or 99)` which misscored a perfect `iters==0` result — true first-pass is 21/23, not 2/23 `infra`
- [x] **P0.12** Nightly CI runs the real pipeline+model — **done (commit 9627a8d).** `bench/leaf/nightly.sh` is the cron entry point: it checks the local model is reachable (a nightly "passing" against a dead model is a lie), runs the leaf benchmark end-to-end (the model fills every subject), and appends a timestamped scorecard summary to a history log OUTSIDE the repo (survives `git reset --hard` syncs) + optional ntfy. Installed as a **box-local cron** (Jesse's call — the model lives on the box): `0 4 * * * bash …/bench/leaf/nightly.sh # alchemist-nightly`. Fail-loud on down-model/regression. Closes the standing "CI never runs the model" gap. `infra`
- [x] **P0.13** Deterministic replay — **done (commit e43e59a, `implementer/tdd_generator.py` — `_deterministic` mode gated on `ALCHEMIST_DETERMINISTIC`).** Found the non-determinism source: even the FIRST fill ran at temp 0.15 (and the multi-sample fan-out at 0.35). New `ALCHEMIST_DETERMINISTIC` env forces greedy decode (temp 0) at every model call in the fill loop AND collapses the multi-sample fan-out to a single greedy sample; the fuzz seed was already fixed. **Empirically proven on box: count_char translated twice with the flag → BYTE-IDENTICAL emitted Rust (`diff` clean), both OVERALL PASS.** Off by default (sampling finds more wins). +2 unit tests. Suite 767. `infra`
- [x] **P0.14** Per-function timing & cost telemetry — **done (commit bf1c1d0; `implementer/tdd_generator.py` captures the per-fill snapshot, `reporter/refusal_ledger.py` emits per-fn + rollup).** `FunctionAttempt` now carries `elapsed_s` / `llm_calls` / `output_tokens`, captured per fill via `self.llm.stats` snapshot deltas around each `_fill_in_function` (tolerant of a shim without `.stats`). The refusal ledger emits them per function plus a subject roll-up (`total_elapsed_s`, `total_llm_calls`, `total_output_tokens`, `slowest_fn`, `costliest_fn`), and the pipeline prints a one-line spend summary. A cached-win restore reads as elapsed>0 / llm_calls==0 — the cheapest outcome, made visible. **Validated on box: crc32b → `telemetry: 0.1s, 0 LLM calls` (cached restore).** +1 rollup test. Suite 761. `infra`

---

## P1 · Whole Small/Mid C Library — Push-Button (IN PROGRESS)

*A never-seen C library → a verified Rust workspace, under 5% refusal, zero human touches. The first genuinely fundable claim.*
**Exit:** 5+ unseen C libs converted hands-off · refusal <5% · signed receipts · a stranger can clone & reproduce.

> **Baseline (2026-07-12, `bench/lib/run_libbench.py`, 8 unseen libs cold):** 4/8 OVERALL PASS (siphash, murmur3, rc4, hashkit), overall function-level refusal 23.5%. Batch surfaced TWO problem classes: (a) shape-coverage refusals (base64_decode binary-out, rc4_keystream, heap alloc/free); (b) **whole libraries producing 0/0 functions** — the dangerous one, invisible to the refusal metric. Both 0/0 cases (sha256, jsmn) were STRUCT-CARRY failures now FIXED: **scalar typedefs (BYTE/WORD → u8/u32; commit 9513ed6) + enum typedefs (jsmntype_t → i32) + `#ifdef`-in-struct-body + Rust-keyword field names (`type`→`r#type`; commit b0f0227).** sha256's SHA256_CTX + jsmn's jsmntok_t/jsmn_parser now carry & compile cold (sha256 went total-failure → normal in-progress fill; the transform is just slow). Then closed a shape-coverage refusal: **new `buf_gen` shape (`<byteptr> f(<size> n, ...) -> Vec<u8>`, commit a29c24a) — `heap:make_buffer` now verifies byte-exact on iter 1 (heap 0/2 → 1/2); generalizes to memset/pattern/PRNG fills.** +8 regression tests.
>
> **Fix wave 2 (2026-07-12, commit 997e546, cold-VALIDATED on box):** TWO whole-library unblocks landed + proven end-to-end. **(1) free/destroy no-op template** (`free_noop_template`, init_templates.py): a `void free_X(ptr)` whose C body is *only* deallocation calls is a no-op in safe Rust (owned Vec/Box drops) — accepted fail-closed (body-confirmed pure-free, else defer to model). **`heap:free_buffer` now verifies → heap 1/2 → 2/2, OVERALL PASS, 0% refusal.** **(2) undefined-error placeholder** (skeleton.py `_lib_rs_for`): the architect sometimes emits a trait method returning `Result<_, SomeError>` without defining `SomeError`, which broke the *whole crate's* compile → 0/0 functions filled. Skeleton now emits a minimal `pub struct SomeError;` + Display for any trait-referenced error type not defined/imported. **`base64` went 0/0 → 1/2: `base64_encode` verifies byte-exact; `base64_decode` still refuses (the binary-out decoder below).** +7 regression tests, suite 777.
>
> **Fix wave 3 (2026-07-12, commits 07020fd→c8bff85, cold-VALIDATED): INVERSE-PAIR ROUNDTRIP ORACLE (P1.15) — base64 0/0 → 1/2 → 2/2 OVERALL PASS.** base64_decode (`char* f(char*)` → `Result<Vec<u8>,E>`) refused with "no verifiable test vectors" (random fuzz strings aren't valid base64). Now the decoder class is unblocked: when a decoder is the inverse of an oracle-able encoder in the same subject, mint valid inputs by running the C ENCODER on random ASCII plaintext and require `decode(encode(p)) == p`. **base64_decode is the first `char*` binary-out decoder the pipeline verifies byte-exact.** Generalizes to inflate/decompress/deserialize. Details in P1.15 below.
>
> **Post-fix aggregate (2026-07-12, fresh cold 8-lib batch on all fixes, `run_libbench.py`):** OVERALL REFUSAL **23.8%** — ~flat vs the 23.5% baseline, but the flatness is misleading: the wins are real and confirmed at scale (**base64 2/2 0%** ✅, **heap 2/2 0%** ✅, murmur3 7/7, hashkit 3/3, siphash 1/1), while the aggregate is dominated by the **two hardest libraries**, which are DIFFERENT problems than the ones fixed: **sha256 0/4** (the 64-round transform is genuinely hard/slow to verify cold — needs a decomposition or longer budget, not a coverage fix) and **jsmn 0/0** (header-only + recursive parser — see below). The refusal % is a blunt whole-library aggregate; per-capability the frontier moved (decoder class + header-only libs are new).
>
> **jsmn diagnosis + two header-only fixes (2026-07-12, commits dd97d92, 32a3df9):** jsmn showed the dangerous 0/0 "invisible failure." Root cause was NOT struct-carry — it was a **`.c`-only assumption in TWO stages**: (1) `module_detector._group_by_file` grouped only `.c` files into modules, so a header-only library (jsmn, stb-style — whole impl in the `.h`) produced **0 modules**; (2) `spec_extractor._extract_module` read function bodies only from `.c`, so even once detected the functions weren't read ("No functions found"). **Both fixed** (the parser only records definitions, so a `.h` with a non-empty `functions` list is a source module; +6 tests). **jsmn now passes analyze → extract → architect cleanly** (6 fns detected, 2 algorithms after static-helper filtering, architecture validated 0 errors) — the invisible 0/0 dead-end is eliminated. **Next jsmn blocker (root-caused, deferred — P2-class):** the skeleton fails to compile with `cannot find type Token`. Precise cause: **`struct_lift.inject_state_shared_types` only carries the `params[0]` STATE struct** (`jsmn_parser` → `ParserState`, keyed on the spec's first-param lift, struct_lift.py:355). `jsmntok_t` appears as a *secondary* parameter — the token-array element type (`tokens: &mut [Token]`) — which struct-carry never emits, and the architect independently renamed it `Token`, so the reference dangles. The general fix is to carry EVERY struct type referenced in ANY function signature (not just params[0]) under the name the spec/architect uses — a real whole-program-type enhancement (P2). Only THEN does the recursive-descent parser itself have to verify (hardest, `research`). jsmn is now a *visible, root-caused* in-progress target, not a silent failure.
>
> **Remaining refusal worklist:** rc4_keystream — verified via the cipher-sequence gate but the per-fn ledger marks it refused (accounting false-negative; needs sequence-member crediting).

- [ ] **P1.1** zlib full workspace green on a FRESH clone (no cached wins) `model`
- [ ] **P1.2** libcrc all-green cold (9/9) from scratch `model`
- [ ] **P1.3** SHA-256 / siphash / base64 / murmur3 cold-green `model`
- [ ] **P1.4** parson (JSON parser) end-to-end `model`
- [ ] **P1.5** tinycbor / a CBOR codec `model`
- [ ] **P1.6** A small container lib (uthash-style) — pointer-heavy `research`
- [ ] **P1.7** A compression codec (heatshrink / miniz) `model`
- [ ] **P1.8** A protocol parser (http-parser subset) — goto-heavy state machine `research`
- [ ] **P1.9** A crypto primitive lib (monocypher subset) — constant-time-sensitive `model`
- [x] **P1.10** Unattended batch runner — N libs, walk away, collect scorecards — `bench/lib/run_libbench.py` (commit c235111): cold-runs a curated lib set, aggregates per-lib + overall function-level refusal + a triage worklist `infra`
- [x] **P1.11** Build-system discovery robustness — already covered by WALL-4 (`verifier/build_c_dll.py::build_c_dll` + `discover_c_build`): non-lib-dir exclusion, amalgamation detection, `main()` filtering, make/cmake `prepare_native_build` `eng`
- [x] **P1.12** Dependency-ordered fill at 50–150 fns — covered by P2-I (`implementer/tdd_generator.py::_topo_sort_algorithms` orders per-module fills leaf-first) `eng`
- [ ] **P1.13** Refusal <5% exit criterion met on an unseen lib `model`
- [x] **P1.16** Header-only C library ingestion — a lib whose whole implementation lives in a `.h` (jsmn, stb-style single-header libs) previously produced 0 modules → 0/0 (silent invisible failure). Fixed the `.c`-only assumption at both sites it appeared: `analyzer/module_detector._group_by_file` (a `.h` with function DEFINITIONS is now a source module; kept in `headers` too so its struct/typedef info still merges into any sibling `.c`; self-association guarded to avoid duplicating its own structs) and `extractor/spec_extractor._extract_module` (reads bodies from `.c` AND `.h/.hpp/.cc/.cpp/...`; safe — the parser records only definitions and the module-membership guard keeps us to the module's own functions). **jsmn now passes analyze→extract→architect clean** (6 fns detected, architecture validated 0 errors; commits dd97d92, 32a3df9; +6 tests). Full jsmn verify is gated on a P2-class architect↔struct-carry type-rename coordination issue (the architect renames `jsmntok_t → Token` but struct-carry emits the original name) + recursive-parser verification — see the P1 note above. `eng`
- [x] **P1.15** Inverse-pair roundtrip oracle — unblocks the DECODER class (base64_decode, inflate, decompress, deserialize). **DONE + cold-VALIDATED on box: base64 0/0 → 1/2 → 2/2 OVERALL PASS (0% refusal); base64_decode is the first `char*` binary-out decoder the pipeline verifies byte-exact through all 5 gates.** When a `char* f(char*)` decoder is the declared inverse of an oracle-able encoder in the same subject (`_paired_encoder_name` table: decode↔encode, decompress↔compress, inflate↔deflate, …), mint valid inputs by running the compiled C ENCODER on random plaintext and require `decode(encode(p)) == p` — the encoder is the C reference, so it's a sound differential; the lossy C decoder is never called. 7 sites (commits 07020fd→c8bff85): `classify_cstr_roundtrip` + `fuzz_cstr_roundtrip_vectors` + vector-synth dispatch + `build_diff_config` harness (all BEFORE cstr_out) in auto_config.py; `cstr_roundtrip` adapter (Rust decoder→Vec<u8> + uniquely-named `c_<decoder>_enc` encoder wrapper) in adapter_gen.py; `_proptest_cstr_roundtrip_block` (mint-via-encoder, assert identity) in proptest_gen.py; `_emit_roundtrip_test` (`.unwrap()`-based, no `E: PartialEq`) + `_roundtrip_` fill-loop test filter in tdd_generator/test_generator. **Four real bugs found & fixed via cold iteration:** (a) tdd_generator's own backfill re-mints vectors and had no roundtrip branch → wired it in; (b) `_test_filters_for_fn` omitted `_roundtrip_` → fill loop ran 0 tests → false "no test vectors"; (c) encoder-failure (NULL/empty output) minted bogus `decode("")==<bytes>` vectors → skip them; (d) **base64's C encoder indexes its table by a SIGNED `char` → UB on plaintext bytes ≥128 → garbage output a memory-safe decoder can't match → restrict minted plaintext AND the proptest strategy to ASCII (1..127).** +12 regression tests (test_cstr_roundtrip_shape.py). `eng`
- [~] **P1.14** Cold-start reproducibility + signed receipt — receipt engine DONE (`verifier/receipt.py`: sealed receipt w/ content-SHA256 + optional HMAC via `ALCHEMIST_RECEIPT_KEY`, records gates/harnesses/oracle/env; `verify_receipt_integrity` recomputes) + deterministic-replay mode (P0.13). Remaining: a documented stranger-clone reproduce run. `infra`

---

## P2 · Scale — Large Single C Codebase (MID)

*A 30k–100k-LOC C project (SQLite core, lwIP) → a verified Rust workspace over a long, resumable, unattended run.*
**Exit:** SQLite (or lwIP) core → verified workspace, honest refusals, resumable across days.

- [ ] **P2.1** Call-graph partitioning + bottom-up scheduling across 1000s of fns `eng`
- [ ] **P2.2** Cross-module type universe at 1000s of types `eng`
- [ ] **P2.3** Pipeline throughput & memory profiling at scale `eng`
- [ ] **P2.4** Parallel fill fleet with backpressure + transient-error isolation `eng`
- [ ] **P2.5** Persistent run journal (SQLite-backed) `infra`
- [ ] **P2.6** Multi-day resumability + crash recovery `eng`
- [ ] **P2.7** Deterministic large runs `infra`
- [ ] **P2.8** 1000-function progress dashboard `infra`
- [ ] **P2.9** Coverage & unverifiable ledger at scale `infra`
- [ ] **P2.10** SQLite core milestone `model`
- [ ] **P2.11** lwIP (network stack) milestone `research`
- [ ] **P2.12** Hybrid C/Rust link-back at scale `eng`

---

## P3 · C++ Frontier (FAR)

*Prove the C++ capability stack (built in SEM) on real targets. ArduPilot is majority C++; the pipeline is C-first today.*
**Exit:** a header-only C++ lib + a small C++ project (classes, templates, RAII) → verified idiomatic Rust.

- [ ] **P3.1** C++ tree-sitter analyzer + TU model `eng`
- [ ] **P3.2** C++ reference-oracle build + mangling-aware FFI `eng`
- [ ] **P3.3** Header-only C++ library milestone `research`
- [ ] **P3.4** A small class-based C++ project `research`
- [ ] **P3.5** A mid C++ library with templates + STL `research`
- [ ] **P3.6** Method-call differential harness `eng`
- [ ] **P3.7** C++ refusal taxonomy proven (multiple inheritance, heavy TMP flagged) `eng`
- [ ] **P3.8** C++ idiomaticity bar — traits/generics/ownership, not transliterated C++ `research`

---

## P4 · Embedded & the Unsafe Boundary (FAR)

*Where "perfect safe Rust" meets physics. Draw the unsafe boundary in exactly the right place and audit it.*
**Exit:** a real driver → safe algorithmic Rust + a thin, audited, clearly-marked unsafe HAL shim, verified at the boundary.

- [ ] **P4.1** no_std translation path `eng`
- [ ] **P4.2** Safe-vs-irreducibly-unsafe classifier `unsafe`
- [ ] **P4.3** A real embedded driver end-to-end (IMU/sensor) `unsafe`
- [ ] **P4.4** Boundary verification — safe-core differential + shim contract tests `eng`
- [ ] **P4.5** Unsafe-audit report — every block justified, minimized, reviewed `unsafe`
- [ ] **P4.6** RTOS abstraction shim milestone (ChibiOS/NuttX primitives → traits) `unsafe`
- [ ] **P4.7** Static-allocation / no-heap path proven `eng`
- [ ] **P4.8** Timing-preservation validation `unsafe`

---

## P5 · ArduPilot (FRONTIER)

*The dream target, in flyable slices. Algorithmic layers first (verified), then the boundary, with SITL as the behavioral oracle.*
**Exit:** AP_Math / filters / CRC verified byte-exact · a control subset behaviorally matched in SITL · a flyable-in-simulation Rust slice.

- [ ] **P5.1** Ingest the ArduPilot build (waf) + board configs `eng`
- [ ] **P5.2** Cross-library dependency graph `eng`
- [ ] **P5.3** Feature / board conditional resolution `research`
- [ ] **P5.4** AP_Math → verified Rust (vectors, matrices, quaternions) `model`
- [ ] **P5.5** Filters & EKF math kernels `research`
- [ ] **P5.6** AP_CRC / checksums (extend ardupilot_crc_verified) `eng`
- [ ] **P5.7** Coordinate / geodesy math `model`
- [ ] **P5.8** AP_HAL utility / logic (non-hardware) `eng`
- [ ] **P5.9** Control math (PID, attitude/position) `research`
- [ ] **P5.10** Embedded Lua scripting engine (ArduPilot embeds Lua — F.12 lands here) `model`
- [ ] **P5.11** MAVLink → Rust `research`
- [ ] **P5.12** Parameter system → Rust `eng`
- [ ] **P5.13** DataFlash / logging format `eng`
- [ ] **P5.14** Sensor drivers (IMU/baro/GPS) — safe logic + audited unsafe shim `unsafe`
- [ ] **P5.15** Bus drivers (I2C/SPI/UART) — audited unsafe `unsafe`
- [ ] **P5.16** Scheduler / real-time loop — timing-preserving `unsafe`
- [ ] **P5.17** SITL as the behavioral oracle — diff flight logs across scenarios `research`
- [ ] **P5.18** Flight-envelope scenario corpus `infra`
- [ ] **P5.19** Incremental fly-in-SITL milestones `research`
- [ ] **P5.20** Full-vehicle subset flyable on Rust `research`
- [ ] **P5.21** HIL / bench validation `unsafe`
- [ ] **P5.22** Safety / certification-mindset audit of the unsafe boundary `unsafe`

---

## P6 · Autonomy — Point & Walk Away (CONTINUOUS)

*`alchemist translate <repo>` runs unattended for hours→days and returns verified Rust + an honest refusal report.*
**Exit:** one command · unattended · resumable · verified workspace + a per-subsystem "% verified / % refused / why" report you can trust.

- [ ] **P6.1** Long-run orchestrator (hours→days, resumable, crash-safe) `eng`
- [ ] **P6.2** Refusal queue + auto-escalation `eng`
- [ ] **P6.3** Human-in-the-loop patch UX `eng`
- [ ] **P6.4** Live repo-scale dashboard `infra`
- [ ] **P6.5** Model-routing tiers (cheap→strong by difficulty) `infra`
- [ ] **P6.6** Distributed fill fleet `eng`
- [ ] **P6.7** Global regression vault `infra`
- [ ] **P6.8** Repo-scale signed receipts `infra`
- [ ] **P6.9** One-command UX + docs `eng`
- [ ] **P6.10** Coverage & honesty report (% verified / % refused / why) `infra`
- [ ] **P6.11** Continuous re-verification on upstream drift `eng`
- [ ] **P6.12** Buildable, tested output workspace `eng`

---

## Track · SEM — C/C++ Semantics Coverage

*Every C/C++ construct gets a sound, verified translation strategy — or an honest refusal. The correctness-completeness backbone.*
**Exit:** no construct silently mistranslated. Aliasing, unions, and UB respected, not ignored.

**Memory & pointers**
- [ ] **SEM.1** Pointer provenance & aliasing model — C's unrestricted aliasing → Rust's borrow model (the #1 hard problem) `research`
- [ ] **SEM.2** restrict/noalias exploitation → non-overlapping slice APIs `research`
- [ ] **SEM.3** Pointer arithmetic → slice/index or raw-ptr-in-unsafe with bounds proof `research`
- [ ] **SEM.4** Out-of-bounds-by-design (one-past-end, sentinels) → safe iterators/slices `research`
- [ ] **SEM.5** Multiple mutable aliases / shared mutable state → Cell/RefCell/split-borrow/indices `research`
- [ ] **SEM.6** container_of / offsetof / intrusive structures → safe ownership `research`
- [ ] **SEM.7** Tagged / low-bit-stashed pointers → safe encodings `research`
- [ ] **SEM.8** Null-pointer semantics → Option<&T>/Option<NonNull> `eng`
- [ ] **SEM.9** void* generic pointers → generics/enums/Box<dyn Any> `research`

**Memory model & UB**
- [ ] **SEM.10** Uninitialized memory reads → MaybeUninit or refuse `eng`
- [ ] **SEM.11** Type punning via union → safe tagged enum / transmute-with-proof `research`
- [ ] **SEM.12** Type punning via memcpy/reinterpret → from_ne_bytes/to_ne_bytes `eng`
- [ ] **SEM.13** Strict-aliasing violations in real C → detect + preserve behavior `research`
- [ ] **SEM.14** Signed-overflow UB → wrapping/checked/saturating by intent `eng`
- [ ] **SEM.15** Shift/division UB (shift≥width, INT_MIN/-1) → guarded ops `eng`
- [ ] **SEM.16** Integer promotion & implicit conversion → explicit value-preserving casts `eng`
- [ ] **SEM.17** sizeof/offsetof/alignment/#[repr(C)] layout fidelity `eng`
- [ ] **SEM.18** Endianness-dependent code → explicit be/le ops `eng`
- [ ] **SEM.19** Packed structs & unaligned access → #[repr(packed)] + read_unaligned `eng`
- [ ] **SEM.20** Flexible array members → slice-tail / DST `research`
- [ ] **SEM.21** Anonymous structs/unions → nested Rust types `eng`
- [ ] **SEM.22** Bitfields → generated accessors, byte-exact `eng`

**Control flow & functions**
- [ ] **SEM.23** Computed goto / labels-as-values → state-machine lowering `research`
- [ ] **SEM.24** setjmp/longjmp → structured control flow / Result or refuse `research`
- [ ] **SEM.25** Variadic functions → refuse-or-shim `unsafe`
- [ ] **SEM.26** Function pointers & typedef'd signatures → fn ptr/dyn/enum `research`
- [ ] **SEM.27** Recursion & deep call graphs — stack-safety analysis `eng`
- [ ] **SEM.28** Comma operator / sequence points / eval order preserved `eng`

**Preprocessor**
- [ ] **SEM.29** Object-like & function-like macros → const/fn/inline, expansion-faithful `research`
- [ ] **SEM.30** Token pasting (##) & stringization (#) `research`
- [ ] **SEM.31** X-macros / macro-generated code → expand-then-translate `research`
- [ ] **SEM.32** Conditional compilation matrix (#if/#ifdef) `research`
- [ ] **SEM.33** Include-graph & translation-unit modeling `eng`

**Qualifiers, atomics, concurrency, platform**
- [ ] **SEM.34** volatile → read_volatile/write_volatile (MMIO) `unsafe`
- [ ] **SEM.35** _Atomic + memory ordering → std::sync::atomic with correct Ordering `research`
- [ ] **SEM.36** C11 threads/pthreads → std::thread + sync primitives `research`
- [ ] **SEM.37** Thread-local storage → thread_local! `eng`
- [ ] **SEM.38** Data-race detection & safe mapping `research`
- [ ] **SEM.39** libc calls → std/libc mapping `eng`
- [ ] **SEM.40** errno / signals `research`
- [ ] **SEM.41** __attribute__ handling (packed, aligned, noreturn, weak, section) `eng`
- [ ] **SEM.42** Compiler builtins & intrinsics (__builtin_*, SIMD) `research`
- [ ] **SEM.43** Inline assembly → refuse + flag `unsafe`
- [ ] **SEM.44** K&R / old-style declarations `eng`

**C++**
- [ ] **SEM.45** class → struct + impl `eng`
- [ ] **SEM.46** Access control → visibility `eng`
- [ ] **SEM.47** Single inheritance → composition + trait `research`
- [ ] **SEM.48** Multiple inheritance → refuse/flag `unsafe`
- [ ] **SEM.49** Virtual inheritance → refuse/flag `unsafe`
- [ ] **SEM.50** Virtual dispatch → dyn Trait / enum-dispatch `research`
- [ ] **SEM.51** vtable layout fidelity (for FFI) `research`
- [ ] **SEM.52** Abstract base → trait `eng`
- [ ] **SEM.53** Constructors → assoc fns / builders `eng`
- [ ] **SEM.54** Destructors / RAII → Drop `eng`
- [ ] **SEM.55** Operator overloading → std::ops `eng`
- [ ] **SEM.56** Copy/move semantics → Clone/move `research`
- [ ] **SEM.57** References & const& → borrows `research`
- [ ] **SEM.58** Templates → generics + bounds `research`
- [ ] **SEM.59** Template specialization → impls/where `research`
- [ ] **SEM.60** Non-type template params → const generics `eng`
- [ ] **SEM.61** SFINAE / concepts → trait bounds `research`
- [ ] **SEM.62** Template metaprogramming → refuse/flag `unsafe`
- [ ] **SEM.63** STL containers → std `eng`
- [ ] **SEM.64** Iterators → Rust iterators `eng`
- [ ] **SEM.65** Smart pointers → Box/Rc/Arc `research`
- [ ] **SEM.66** Exceptions → Result/panic policy `research`
- [ ] **SEM.67** Namespaces → modules `eng`
- [ ] **SEM.68** Name mangling & overload resolution `research`
- [ ] **SEM.69** Lambdas/closures → Rust closures `eng`
- [ ] **SEM.70** constexpr/consteval → const fn `research`

---

## Track · VER — Verification & Formal Methods

*From differential testing toward equivalence proof. Every function earns a sound gate — or an honest refusal.*
**Exit:** zero unverified emissions · each fn tagged with its proof method · cyclic cores verifiable · the oracle itself audited.

- [~] **VER.1** Byte-exact FFI differential (harden/generalize any signature) `eng` — **cstr_out shape ADDED (P0.8a, commits 189648c+69a3b08):** `char* f(char*)` text transforms now synthesize C-reference vectors + str_exact tests; also fixed the fill-loop filter that dropped `_str_`/`_body_` test schemes. **base64: 100%→50% refusal, base64_encode byte-exact verified.** Remaining: binary-out `char* f(char*)` (base64_decode → `Result<Vec<u8>>`) — needs roundtrip-mint or a byte-return (length-aware) adapter, since the C `char*` return is NUL-lossy for binary.
- [~] **VER.2** Whole-program e2e observable differential — wired; now exercise widely `eng`
- [ ] **VER.3** Stateful sequence differential (generalize state_mutator) `eng`
- [ ] **VER.4** Coverage-guided fuzz-vector generation `eng`
- [ ] **VER.5** Sanitizer-diff verdict engine — wire sanitizer_diff (C-buggy classification) `wire`
- [ ] **VER.6** Miri UB-freedom gate at scale `eng`
- [ ] **VER.7** Property/roundtrip test synthesis `eng`
- [ ] **VER.8** Metamorphic relations for reference-less code `research`
- [ ] **VER.9** KAT/standards catalog (FIPS/RFC) auto-lookup `infra`
- [ ] **VER.10** Translation validation (bounded equivalence) `research`
- [ ] **VER.11** Kani (bounded model checking) integration `research`
- [ ] **VER.12** Deductive proof (Prusti/Creusot/Verus) `research`
- [ ] **VER.13** Aeneas-style functional translation validation `research`
- [ ] **VER.14** Optimization-invariance equivalence `research`
- [ ] **VER.15** Float/fixed-point differential (tolerance + bit-exact) `research`
- [ ] **VER.16** Concurrency verification (loom) `research`
- [ ] **VER.17** Side-channel / constant-time preservation `research`
- [ ] **VER.18** Oracle provenance & signed receipts (extend signet) `infra`
- [ ] **VER.19** Callback / higher-order-fn differential `research`
- [ ] **VER.20** Unverifiable taxonomy + refusal policy `eng`
- [ ] **VER.21** Verification cost model (rigor scaled to risk) `infra`
- [ ] **VER.22** Mutation-test the ORACLE itself (is the gate sound?) `research`
- [ ] **VER.23** Regression vault — re-verify every conquered fn `infra`
- [ ] **VER.24** Per-fn cross-domain coverage report `infra`
- [ ] **VER.25** "Divergence = a proven C bug" write-up `research`

---

## Track · MODEL — Model & Generation

*Get the most from a local model — and close the self-improvement loop. The model isn't the bottleneck; the harness is. US-origin models only.*
**Exit:** high first-pass fill rate via better prompting, retrieval, repair, and a fine-tune on the tool's own verified conversions.

- [ ] **MODEL.1** Spec-first chain-of-thought (refine) `model`
- [ ] **MODEL.2** Best-of-N + self-consistency (tune n/temp/selection) `model`
- [ ] **MODEL.3** Verification-in-the-loop generation (feed exact error back) `eng`
- [ ] **MODEL.4** RAG over prior VERIFIED conversions `research`
- [ ] **MODEL.5** Self-training corpus harvest (every verified conversion is a pair) `research`
- [ ] **MODEL.6** Fine-tune Gemma-4-31B on the verified corpus (US-origin) `research`
- [ ] **MODEL.7** Distill a specialized translation model `research`
- [ ] **MODEL.8** Grammar-constrained decoding to valid Rust `research`
- [~] **MODEL.9** Context management for large fns (32k overflow hit the architect this session) `eng`
- [ ] **MODEL.10** Whole-module / long-context prompting `eng`
- [ ] **MODEL.11** Model eval harness (per-model success on the benchmark) `infra`
- [ ] **MODEL.12** Model routing by difficulty `infra`
- [ ] **MODEL.13** Multi-model ensemble/vote (Gemma, Llama-4) `research`
- [ ] **MODEL.14** Prompt-library versioning + A/B `infra`
- [ ] **MODEL.15** Reference-C + macro injection (harden) `eng`
- [ ] **MODEL.16** Decomposition prompting for hard fns (extend structural_decomp) `eng`
- [ ] **MODEL.17** Mechanical-mistake prompt hardening (pairs with cargo-fix lever) `model`
- [ ] **MODEL.18** Idiomaticity prompting (non-regressive) `model`
- [ ] **MODEL.19** Cost/latency budgeting per fn `infra`
- [ ] **MODEL.20** Local-serving reliability (vLLM :8086, not dead :8090; failover) `infra`
- [ ] **MODEL.21** Determinism controls (temp=0 replay path) `infra`

---

## Track · IDIOM — Idiomaticity & Quality

*The Rust must be genuinely good — idiomatic, clippy-clean, ergonomic — not a transliteration. Verified-preserving, always.*
**Exit:** output a Rust engineer would accept in review, correctness never traded for style.

- [ ] **IDIOM.1** Transliteration → idiomatic pass (verified-preserving) `eng`
- [ ] **IDIOM.2** Raw index loops → iterators `eng`
- [ ] **IDIOM.3** Sentinel/null returns → Option/Result `eng`
- [ ] **IDIOM.4** Manual buffers → slices/Vec/arrays `eng`
- [ ] **IDIOM.5** Error codes → Result + error enums `eng`
- [ ] **IDIOM.6** clippy-clean output gate `eng`
- [ ] **IDIOM.7** rustfmt-clean output `eng`
- [ ] **IDIOM.8** Idiomatic ownership inference (borrow vs own) `research`
- [ ] **IDIOM.9** Doc-comment carry/generation `eng`
- [ ] **IDIOM.10** Ergonomic public API design `research`
- [ ] **IDIOM.11** Module/crate structure quality `eng`
- [ ] **IDIOM.12** Idiomaticity scored & regression-gated `infra`

---

## Track · PERF — Performance Parity

*The Rust must match or beat the C. A slower translation is a rejected translation.*
**Exit:** every conquered subject benchmarked; Rust ≥ C on time/size/allocation, with a regression gate.

- [ ] **PERF.1** Perf-parity gate threaded into the receipt (perf.py exists) `wire`
- [ ] **PERF.2** Benchmark suite per subject `infra`
- [ ] **PERF.3** Zero-cost-abstraction verification `eng`
- [ ] **PERF.4** Bounds-check elision where provably safe `research`
- [ ] **PERF.5** Binary-size parity `eng`
- [ ] **PERF.6** Allocation-behavior parity `eng`
- [ ] **PERF.7** SIMD / vectorization preservation `research`
- [ ] **PERF.8** Perf-regression gate across runs `infra`

---

## Track · INFRA — Infrastructure, Eval & Product

*The harness, the metrics, the trust story, and the path to funding.*
**Exit:** a public benchmark + leaderboard, reproducible signed receipts, one-command UX, a flagship dogfood demo, and a clear DARPA-TRACTOR/SBIR posture.

- [ ] **INFRA.1** The eval harness / leaderboard `infra`
- [ ] **INFRA.2** Public unseen-library benchmark set `infra`
- [ ] **INFRA.3** CI runs the real pipeline+model nightly `infra`
- [ ] **INFRA.4** Reproducible runs (pinned toolchains, seeds, model versions) `infra`
- [ ] **INFRA.5** Product-grade signed conversion receipts `infra`
- [ ] **INFRA.6** One-command UX (`alchemist translate <path>`) `eng`
- [ ] **INFRA.7** Repo-scale live dashboard `infra`
- [ ] **INFRA.8** Resumable/crash-safe long runs (journal) `eng`
- [ ] **INFRA.9** Distributed fill fleet `eng`
- [ ] **INFRA.10** Cost accounting & budgets `infra`
- [ ] **INFRA.11** Coverage/honesty report (% verified/refused/why) `infra`
- [ ] **INFRA.12** Documentation site + user guide `infra`
- [ ] **INFRA.13** Buildable, tested output workspace `eng`
- [ ] **INFRA.14** Converter supply-chain security `infra`
- [ ] **INFRA.15** DARPA TRACTOR alignment & positioning `product`
- [ ] **INFRA.16** SBIR / dual-use framing (NV013 lineage) `product`
- [ ] **INFRA.17** Flagship dogfood demo (convert a recognizable dependency) `eng`
- [ ] **INFRA.18** Open-source posture & licensing (Apache-2.0) `product`
- [ ] **INFRA.19** Publish the verified C→Rust pair dataset (research asset + moat) `research`
- [ ] **INFRA.20** Continuous re-verification on upstream drift `eng`

---

## Critical path

`F → P0 → P1 → P2 → P3 → P4 → P5 → P6`, with tracks **SEM · VER · MODEL · IDIOM · PERF · INFRA** running alongside continuously. Vertical phases are integration checkpoints; tracks are the capabilities that feed them. The nearest fundable milestone is the **P1 exit**: an unseen real C library, converted hands-off, verified, under 5% refusal.

## Caveats (honest)

- **Physics:** "perfect *safe* Rust for all of ArduPilot" is unachievable as stated — register access, DMA, and ISRs are irreducibly unsafe. The real deliverable is verified safe Rust for the algorithmic layers + a thin, audited, clearly-marked unsafe hardware shim.
- **Research:** `research`-tagged items are open problems, not schedule you can burn down on weekends. The whole ladder rests on the reliability floor (P0) holding.
