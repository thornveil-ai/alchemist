# Alchemist Battle Plan — from "one algorithm" to "any C/C++ → safe Rust"

> **North Star:** point Alchemist at *any* C or C++ and get back **verified safe Rust —
> byte-exact-or-refused — with minimal human input, at scale.**
> This file is the running battle plan. Check items off as they land. Every claim of
> "done" must be backed by a live run, not a doc.

## Invariants (never traded away)
- [ ] **Byte-exact-or-refused** — the pipeline refuses success rather than shipping wrong code.
- [ ] **Safe Rust by default** — no `unsafe` unless explicitly gated + justified.
- [ ] **Local models only** (US-origin), zero cloud, zero data egress.
- [ ] **Verification is the product** — translation is cheap, *proof* is the moat.

---

## GROUND TRUTH — measured live 2026-07-07 (not claimed)

**What actually works autonomously:**
- Known-pattern **stateless single algorithms** (adler32, crc32, siphash, sha256-class):
  spec-first → generate → differential byte-exact. Real.

**What was human-in-the-loop:**
- **zlib** (whole stateful library): byte-exact + complete, but the hard functions
  (state machines, `deflate_stored`) were **hand-ported** with the verifier keeping us honest.

**The walls, observed on a cold RC4 run:**
- **WALL 1 — Triage rejects the unknown.** RC4 (real stateful cipher) was classified
  `glue` and **skipped — 0 LLM calls, nothing generated.** The classifier only fires on a
  small `ALGORITHM_PATTERNS` catalog; everything else defaults to glue. **This is the #1
  blocker to "any C."**
- **WALL 2 — Stateful oracle.** Even past triage, verifying a stateful function needs a
  differential *shim* (poke/read state). `shim_synth` exists (promoted) but isn't wired
  into the pipeline.
- **WALL 3 — Control-flow structuring.** `goto`/irreducible state machines have no
  mechanical C→safe-Rust path yet (done by hand for zlib).
- **WALL 4 — Build/harness detection.** Real libraries have build systems; the reference
  DLL + harness are still semi-manual per subject.

---

## PHASE 0 — Instrument & ground (know the real numbers) — ✅ COMPLETE 2026-07-07
*Goal: never again guess what it can do. Measure.*
- [x] **Cold-start benchmark suite** — 8 never-seen C functions across classes (math, bits,
      checksum, string, parser, stateful cipher/PRNG/allocator). `bench/cold_start/cold_bench.py`.
- [x] **Autonomy scorecard per run** — triaged? per-stage PASS/FAIL? LLM calls? overall? —
      **zero human touches** as the bar. Emits `RESULTS.md` + `results.json`.
- [x] **Baseline published (honest numbers, n=8):** triaged-in **12%**, passed-implement
      **12%**, passed-verify **0%**, **OVERALL cold autonomous 0%**. See `bench/cold_start/RESULTS.md`.
- [x] **Regression gate** — the harness is re-runnable on every pipeline change; baseline is
      the number to beat. (Local/box gate, not stock CI — needs a local model. See README.)

**Phase 0 verdict:** cold, the pipeline autonomously translates **0/8** never-seen functions.
**7/8 are skipped at triage with 0 LLM calls** (WALL 1). The one attempted (`parse_int`)
reached `verify` and failed the differential. → Phase 1 is empirically the #1 unlock.

## PHASE 1 — Any single C **function** (autonomous)
*Kill WALL 1. Goal: hand it one arbitrary self-contained C function → verified Rust, no config.*
- [ ] **Replace pattern-catalog triage with a real classifier.** Default should be "attempt
      translation," not "skip as glue." Glue is the *exception*, proven, not the default.
- [ ] LLM- or embedding-based **algorithm/effect detection** (does this compute something
      verifiable?) instead of a name/keyword whitelist.
- [ ] **Auto-synthesize the differential harness for any signature** (scalar in/out, buffers,
      structs) — generalize `verifier/auto_config.py` beyond scalar subjects.
- [ ] **Auto-oracle for pure functions**: compile the C as reference, fuzz inputs, diff.
- [ ] Handle **headerless / partial** C (the onboarding quirk) robustly.
- [ ] Best-of-N + diagnose-repair loop on the fill (already prototyped) wired to the shipping path.
- [ ] **Target: ≥80% of cold single stateless functions pass differential with 0 human touches.**
- [ ] **Target: cold RC4-class stateful single fn passes** (needs Phase 2 oracle).

## PHASE 2 — Any single C **library** (stateful, autonomous)
*Kill WALLs 2–4. Goal: point at a small real library dir → verified Rust workspace.*
- [ ] **Wire `shim_synth` into the pipeline** — auto-generate the stateful poke/read shim
      from struct fields (kills the hand-written-shim requirement).
- [ ] **State-mutator differential oracle**: snapshot struct state across calls, diff vs C.
- [ ] **Auto build/harness detection** (WALL 4): parse Makefile/CMake, build the C reference
      DLL/.a automatically, no per-subject hand config.
- [ ] **Control-flow structuring pass** (WALL 3): mechanical `goto` → labeled-break/loop/
      state-enum transform, verified equivalent. Seed from the zlib inflate state machine.
- [ ] **Whole-library type unification**: one coherent Rust type model across modules
      (`architect/type_unifier` at library scale).
- [ ] **Dependency-ordered fill**: translate leaf functions first, bottom-up.
- [ ] **Auto round-trip discovery**: detect encode/decode or compress/decompress pairs and
      generate the round-trip oracle automatically.
- [ ] **Target: a never-seen small library (e.g. a hash lib, a codec) → verified workspace,
      < 3 human interventions.** Measure and publish.

## PHASE 3 — Whole program / multi-file / real projects
- [ ] Multi-file / multi-module dependency graph → crate/workspace layout automatically.
- [ ] **Preprocessor reality**: `#ifdef` config matrices, macros-as-code, conditional compilation.
- [ ] Global state & init ordering (`architect/global_state`) at project scale.
- [ ] FFI-preserving **incremental migration**: translate module N, keep the rest C, verify
      at the ABI boundary (so huge projects convert piece-by-piece, always green).
- [ ] Function pointers, callbacks, vtable-like C patterns → safe Rust (traits/enums).
- [ ] Unions / type-punning → safe `enum`/`#[repr]` mappings, verified.
- [ ] **Target: a real ~10–50k LOC C project (e.g. a parser lib, a small VM) migrated
      module-by-module with the whole thing staying byte-exact at each step.**

## PHASE 4 — C++ expansion
- [ ] C++ front-end (tree-sitter-cpp or libclang) in the analyzer.
- [ ] **Classes → structs + impls**; constructors/destructors → `new`/`Drop`.
- [ ] **RAII → ownership/borrows**; smart pointers → `Box`/`Rc`/`Arc`.
- [ ] **Templates → generics** (monomorphization-aware); template specialization.
- [ ] **Exceptions → `Result`** (or `panic` where semantics demand), verified equivalent.
- [ ] `std::` containers → Rust `std` equivalents with behavioral differential tests.
- [ ] Virtual dispatch → trait objects; multiple inheritance → composition, verified.
- [ ] **Target: a self-contained C++ class + template translated + differentially verified.**

## PHASE 5 — Scale (thousands → millions of lines)
- [ ] **Sharding & parallelism**: translate thousands of functions concurrently (workflow-style).
- [ ] **Retrieval at scale**: idiom/pattern catalog that grows and is retrieved per function
      (compounding — cracked-once lands first-try elsewhere).
- [ ] **Incremental re-verification**: change one function, re-diff only its blast radius.
- [ ] **Cost/latency budget controls**: translate-to-a-budget; prioritize hot/critical modules.
- [ ] **Caching & resume**: never re-translate an unchanged, already-verified function.
- [ ] **Target: a 100k+ LOC library (e.g. a real crypto or compression stack) fully migrated,
      byte-exact, with a published human-touch count.**

## PHASE 6 — Arbitrary domains (the "truly anything" frontier)
- [ ] **Kernel/driver code**: hardware register access, `volatile`, memory-mapped IO →
      safe abstractions (or explicitly-gated `unsafe` with proof obligations).
- [ ] **Embedded / no_std**: bare-metal, interrupt handlers, fixed-point math.
- [ ] **Concurrency**: pthreads/atomics/locks → `std::thread`/`Arc<Mutex>`/atomics, verified
      race-free (beyond what `concurrency.py` sketched).
- [ ] **Inline assembly** boundaries: identify, isolate, and gate.
- [ ] **Undefined-behavior handling**: when C relies on UB, the sanitizer-diff verdict
      (`c-buggy`) decides — "match C, or prove C is buggy" (promoted; wire it in).
- [ ] **Non-determinism**: time, RNG, IO — model as injected effects, verify the pure core.
- [ ] **Target: translate a driver-class module and a concurrent module, each verified.**

## PHASE 7 — Full autonomy & product
- [ ] **Zero-config `alchemist translate <anything>`**: download → detect → build → translate
      → verify → report, no per-subject setup.
- [ ] **Assurance ladder** (`PATH_TO_FLAWLESS`): L0 compiles → L5 bounded proof (Kani/Miri),
      per-function, with **signed verification receipts**.
- [ ] **Miri UB gate + sanitizer-diff** on by default where toolchain allows (both promoted).
- [ ] **Human-review UX**: surface only the functions the machine is unsure about.
- [ ] **Packaging**: publishable crate output, provenance-attested.
- [ ] **Benchmark vs TRACTOR / c2rust** publicly on shared corpora — % safe, % verified,
      human-touches. Lead on *verified-correct*, not just *compiles*.
- [ ] **Target: a stranger points it at a real library and gets verified safe Rust back.**

---

## Sequencing logic (why this order)
1. **Phase 0 first** — we keep mis-estimating; instrument before building.
2. **Phase 1 is the highest-leverage unlock** — WALL 1 (triage) currently makes "any C"
   *impossible at the front door*. Fixing it turns a dozen supported patterns into "attempt
   anything." Cheap, huge.
3. **Phase 2 is the TRACTOR-parity milestone** — autonomous stateful *library* translation is
   the thing we keep saying we're close to. It's Phases 1+2, honestly scoped.
4. **Phases 3–6 broaden**; **Phase 7 productizes**. Don't start C++ (Phase 4) or scale
   (Phase 5) until a single stateful library is autonomous (Phase 2), or we build breadth on sand.

## The one-line honest status
Today: **best-in-class differential *verifier* + autonomous translator of known-pattern
stateless functions.** The gap to "any C/C++" is **Phase 1 (kill the triage wall) + Phase 2
(autonomous stateful libraries).** Everything past that is breadth on a proven core.
