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

## PHASE 1 — Any single C **function** (autonomous) — ✅ COMPLETE (2026-07-07)
*Kill WALL 1. Goal: hand it one arbitrary self-contained C function → verified Rust, no config.*
**Result: 5/5 clean cold stateless functions verify byte-exact across 5 signature shapes;
UB-bearing C is correctly refused; stateful → Phase 2.**
- [x] **Triage attempts by default** (`patterns.py`): glue requires positive evidence.
      Measured: cold triaged-in **12% → 88%**.
- [x] **Auto-oracle for pure functions** (`auto_config.synthesize_c_vectors`, wired into
      `run_implement_stage`): build the C reference DLL, fuzz it, attach input→output vectors
      so the fill loop can verify code with no standards KATs. **This unlocked the fill.**
- [x] **Headerless / single-`.c`** support: definition-aware `.c` parser in
      `collect_subject_signatures`. Cold single files now yield signatures.
- [x] **Differential harness shapes**: shape-gated not label-gated; accept `char*`; added a
      full **scalar→scalar** shape (classify + auto-oracle + adapter + proptest).
- [x] **First cold autonomous translation achieved**: `fletcher16` (never-seen, headerless)
      → safe Rust, byte-exact vs C, zero human touches.
- [x] **Fill-quality lever** — feed the original C source into the fill prompt (faithful
      translation, not re-invention) + wrapping-arithmetic guidance (match C 2's-complement
      overflow). Turned compile-but-diverge fills into byte-exact ones.
- [x] **In-place buffer shape** (`str_reverse`), **`char*`→`&[u8]`** lift, and **explicit-len
      fill vectors** (`atoib`) — all landed. Five shapes total: checksum, scalar, in-place,
      sqrt, buffer-parse.
- [x] **≥80% of cold stateless functions pass differential** — **exceeded: 5/5 = 100% of
      clean stateless** cold-green. The 2 non-greens (`isqrt`, `parse_int`) are UB-bearing C
      the differential correctly refuses — the contract working, not a miss.
- [x] **Buggy-C is refused, not faked** — byte-exact-or-refused verified end-to-end on real UB.
- [ ] *(moved to Phase 2)* cold RC4-class **stateful** single fn — needs struct-carry + shim.
- [ ] *(nice-to-have, deferred)* LLM/embedding algorithm detection; sanitizer-diff `c-buggy`
      verdict wired into the cold path so UB functions report `c-buggy` instead of a hard refuse.

## PHASE 2 — Any single C **library** (stateful, autonomous) — IN PROGRESS
*Kill WALLs 2 & 4 (WALL 3 = control-flow structuring moved to Phase 3, where irreducible
control flow actually lives; it has no libcrc-class small-library subject). Goal: point at a
small real library dir → **one** verified Rust workspace with a shared type model.*
**Exit-target scope (owner decision 2026-07-08):** Phase 2 closes on the never-seen-library
→ unified-verified-workspace capstone + type unification; WALL 3 (`goto`) and auto-round-trip
discovery are Phase 3. TRACTOR-parity milestone.
- [x] **First stateful function verified cold** — `xorshift_next` (scalar-state mutator,
      `fn(&mut u64) -> u64`), differential over 4000 fuzzed states vs compiled C. Built the
      tracked `struct_lift.py` (C-struct → Rust/FFI field map) + a **scalar-state mutator
      shape** (classify → oracle captures `(return, post-state)` → tuple adapter → proptest),
      with the single-scalar struct carried as `&mut <int>` via a `c_typedefs` override.
- [x] **Multi-field struct carry** — `struct_lift.inject_state_shared_types` emits the safe
      struct (e.g. `Rc4State`) into the crate from the C source, wired before skeleton gen.
      Verified: rc4 now emits `Rc4State`, skeleton compiles past the "cannot find type" wall.
      *(Pointer-field structs like `bump_alloc` are refused by `emit_safe_struct` — still open.)*
- [x] **Sequence oracle** — `classify_cipher_sequence` + a ctypes-struct oracle: **state-observer**
      vectors for `init` (assert each struct field vs C) + **init→keystream sequence** vectors for
      the generator (assert the byte stream). Validated on rc4: 10+10 vectors, keystream matches
      compiled-C RC4 byte-for-byte.
- [x] **Architect crate-layout fix** — reassign trait-referenced error types to the trait's
      crate (kills cross-crate `Rc4Error` undefined) + drop architect-invented state-wrapper /
      builder skeletons that emit unfillable `unimplemented!()` (fixes anti-stub).
- [x] **Whole-crate FFI sequence differential** — `#[repr(C)]` mirror-struct injection +
      `rust_rc4`/`c_rc4` proptest (2000 cases). **rc4 flagship OVERALL PASS cold** — the array-
      struct stateful cipher is translated + byte-exact verified. Second stateful cold-green.
- [x] **`bump_alloc` (raw-pointer field) — cold-green.** The memory-ownership allocator: raw
      `buf` pointer DROPPED from the safe struct, offset logic verified via the **alloc-sequence
      differential** (init + fuzzed op sequence, `Result`→i64, 2000 cases rust-vs-C). Six walls
      cleared incl. triage glue-call-evidence + fill-loop arity guard. **ALL 3 benchmark stateful
      fns (xorshift, rc4, bump_alloc) now cold-green.** *(Follow-up: extract is non-deterministic
      on the capacity param count — harden spec consistency so it's green every run.)*
- [x] **Wire `shim_synth` into the pipeline** — **SUPERSEDED** by the auto-oracle sequence
      differential: we never hand-write a poke/read shim anymore. The compiled-C subject IS
      the oracle; `classify_*_sequence` + the ctypes/FFI mirror drive `init→…→observe` and
      diff every struct field vs C automatically (scalar_mutator / cipher_seq / alloc_seq /
      hash_seq). No separate `shim_synth` wiring is needed for autonomous stateful verify.
- [x] **State-mutator differential oracle**: snapshot struct state across calls, diff vs C.
      Done — the four sequence shapes above ARE this (xorshift/rc4/bump_alloc/fnv cold-green).
- [x] **Auto build/harness detection** (WALL 4): `build_c_dll.discover_c_build` +
      `prepare_native_build` run the library's own make/cmake and materialize generated
      sources; wired at CLI stage-1. Proven on `mathlib` (subdir src + header) and `gentest`
      (Makefile-generated header) — zero hand config.
- [x] **Whole-library type unification**: one coherent Rust type model across modules.
      `workspace_assembler.assemble_workspace` hoists items defined IDENTICALLY in ≥2 modules
      into a shared `<lib>-types` crate the members depend on, and leaves genuinely
      name-conflicting definitions (e.g. crc64's per-variant `crc_tab64`) module-local rather
      than silently merging them. Proven: a 4-module fixture assembles + `cargo build/test
      --workspace` green (`tests/test_workspace_assembler.py`).
- [x] **Dependency-ordered fill**: translate in declaration order so callees fill before the
      composed differential gate (fnv init→update→final cold-green).
- [x] **Unified workspace assembly + receipt**: `lib_orchestrator.assemble_library_workspace`
      + `translate-lib --assemble` gather the PASSING per-module crates into ONE workspace,
      cargo-verify it builds+tests together, and emit `workspace_receipt.json` (members,
      hoisted shared types, conflicts, `human_touches`). The one-type-universe proof.
- [ ] → **Phase 3** **Control-flow structuring pass** (WALL 3): mechanical `goto` →
      labeled-break/loop/state-enum, verified. Deferred — libcrc-class small libraries have no
      irreducible `goto` machines; this belongs with whole-program/real-project control flow
      (already *demonstrated* by hand on the zlib inflate state machine).
- [ ] → **Phase 3** **Auto round-trip discovery**: detect encode/decode or compress/decompress
      pairs and generate the round-trip oracle automatically. Deferred — a whole-program concern.
- [ ] **Target: a never-seen small library → unified verified workspace, < 3 human
      interventions.** Measure and publish. *(Machinery complete + locally cargo-verified;
      awaiting the live libcrc capstone run on the model box for the published touch-count.)*

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
