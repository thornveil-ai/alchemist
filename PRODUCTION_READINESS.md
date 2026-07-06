# Alchemist Production Readiness Report

**Date**: 2026-04-14 (addenda 2026-07-03, **2026-07-06**)
**Status**: Research prototype — methodology now proven on a *whole* library end-to-end and a *second, never-seen* library, autonomously. Still NOT a one-command tool for arbitrary C.

## Addendum 2026-07-06 — byte-exact whole-library + first autonomous never-seen library

Large jumps since the 2026-07-03 addendum below. Several of that report's core
claims are now **superseded** (noted inline); the honest framing still holds.

### 1. zlib is byte-exact end to end (the "non-functional stubs" are gone)
The 2026-07-03 report said "compress/uncompress/inflate/deflate remain
non-functional stubs." **No longer true.** zlib `deflate` **and** `inflate` are
translated to pure safe Rust and verified **byte-identical to the C reference**:
- `deflate` byte-exact at levels 1–9 + `Z_HUFFMAN_ONLY` + `Z_RLE`
- `inflate` byte-exact on stored / dynamic / fixed Huffman streams (LZ77 back-refs)
- **Full round-trip** `Rust deflate → Rust inflate → original` byte-identical:
  21/21 across levels 1/6/9, plus 8/8 large-input (50–90 KB) stress, both raw and
  the standard zlib format (header + adler32 validated). Zero `unsafe`.
- The whole ~30-state `inflate()` machine, `goto`, unions, pointer aliasing, and
  bit-twiddling re-expressed in safe Rust. See `docs/zlib_case_study.md`.

The differential oracle caught ~9 real integration bugs unit tests passed clean
over — the correctness engine works.

### 2. An autonomy layer now exists — and retired 100 items on zlib
New workstreams (`alchemist/autonomy/`, `alchemist/catalog/`), all tested:
- **WS4 diagnose-and-repair loop** — stub → model refill from C → differential
  gate → iterate on the exact discrepancy → verify-or-revert → refuse (never
  fake-green). Proven live: repaired an injected `adler32_z` bug autonomously.
- **WS1 shim synthesis** — auto-generates the mechanical oracle glue from a
  struct's fields (library-agnostic via `c_struct.py`), compile-validated.
- **WS2 type-model inference** — infers the coherent owned-Rust type model from a
  C struct (pointers→`Vec`, indices→`usize`, back-refs flagged) — reproduced
  10/10 zlib decisions from the header alone.
- **WS6 idiom catalog** — `C→safe-Rust` patterns injected per function by signal.
- **M1 autonomy scorecard** — a real metric. **100 items autonomously retired**
  (26 functions differential-proven + 74 oracle shims compile-validated); open
  debt 227 → 127. Every retirement has a proof in `retired_ledger.json`.

### 3. First COMPLETE autonomous translation of a never-seen library (jsmn)
Pointed the agnostic stack at **jsmn** (a JSON tokenizer never seen before) with
zero jsmn-specific code: struct-parse → type-infer → coherent signatures → C
reference oracle → the model filled all 6 functions from C → differential-repair
→ **13/13 byte-exact token streams vs C.** First end-to-end autonomous
translation of a new library. The one hard function cracked not by brute force
but by **diagnosis** — reading the model's output vs the C found a single
coherent-model bug (loop cursor increment placement), fixed first-try once named
and captured as a reusable idiom. See `docs/m2_jsmn_first_swing.md`.

### What this does and does NOT mean
- **Does**: the methodology is proven on a whole hard library (zlib, byte-exact)
  AND a second never-seen library (jsmn, autonomous); the engines are agnostic
  and measured; "hard-frontier" functions are usually *diagnosable* mismatches,
  not model ceilings.
- **Does NOT**: make it one-command for arbitrary C. Still needs WS3 (auto
  control-flow structuring for goto/state-machines), WS5 (build/harness
  detection), the custom-shim tail, and human confirmation of WS2 review flags.
  zlib still has 127 open debt items (the hard stateful tail). See
  `docs/PATH_TO_AUTONOMY.md` for the honest milestone ladder (M0✅ → M1 → M5).

---

## Addendum 2026-07-03 — the differential gate is now real for checksums

What changed since the report below was written:

- **The automated differential path produced its first genuine green.**
  `alchemist verify subjects/zlib -p zlib-checksum` builds the C reference
  DLL, generates FFI bindings and c_*/rust_* adapter wrappers against the
  *actual* generated API (discovered from source, not assumed), and runs
  adler32 + crc32 through 5000 random inputs each against C zlib: 17/17
  differential tests pass with zero hand-editing. Previously the emitted
  diff crate could not even compile (empty lib.rs, orphaned wrappers,
  missing path-deps).
- **crc32's big-endian word braid is fixed at all three layers.** The
  generated `crc_word_big`, the pure-Python fuzz reference, and the locked-in
  regression invariant all implemented (different) wrong variants; all now
  implement zlib's W=8 configuration, anchored against zlib's shipped
  crc32.h table values. zlib-checksum: 183/183 tests pass (was 166/17).
- **Two soundness holes closed.** Unhandled algorithm categories used to fall
  through to a smoke-only "check" that never consulted the C reference —
  they now emit a failing UNVERIFIABLE harness. The test emitter used to
  mangle `Some(18usize)` into `b"Some(18usize)"`, which broke compilation of
  the whole zlib-compression test module and vacuously skipped its gate —
  expected values are now rendered against the function's return type, and
  those 20 tests compile, run, and honestly FAIL against the stub impls.
- **A semantic-lint gate now fails closed on wrong algorithm variants.**
  `scan_workspace_semantics` sweeps every generated fn against its spec at
  verify time; a deliberately-wrong CRC braid variant fails the gate
  (proven by negative test). This is the first real defense against the #1
  failure mode (multi-variant disambiguation) for code that compiles and
  passes vector tests derived from the same wrong assumption.

What did NOT change: `verify` for the full zlib workspace still fails —
correctly — on 42 anti-stub violations (6 of them in zlib-checksum itself:
`make_crc_table`, `braid`, `get_crc_table`, and the other table-generation
helpers are still skeletons) and on the 20 now-honest zlib-compression test
failures. compress/uncompress/inflate/deflate remain non-functional stubs.
**Verified-equivalent today: `adler32_z` and `crc32` (byte-at-a-time public
API), via the automated differential oracle; `crc_word_big` via fixed
vectors against the corrected pure reference (it is `local` in C — not
FFI-observable).**

### Second pass, same day — first all-gates-green crate

- **`alchemist verify subjects/zlib -p zlib-checksum` → `OVERALL: PASS`** —
  the first fully green verification in the project's history. The six
  table-generation skeletons are now real ports (including a complete
  `inflate_table` port whose generated inffixed.h matches zlib's shipped
  file byte-for-byte), anchored against `crc32.h`, so the anti-stub gate is
  clean; test gate 177/0; differential 19/19 incl. new boundary-length
  tests at NMAX/word/braid fold edges.
- **The statics now have a compiled-C oracle.** A checksum shim DLL
  (amalgamated `crc32.c`, W=8/N=5 compile-time-pinned) exports `crc_word`,
  `crc_word_big`, `multmodp`, `x2nmodp`; their fuzz vectors regenerate from
  real compiled zlib and a fail-closed cross-check halts generation on any
  shim-vs-reference disagreement. This independently confirms the W=8 braid
  fix against the actual C (`crc_word_big(1) == 0x9630077700000000`).
- **Claims are artifacts now.** Verify runs emit a content-addressed
  receipt (gates, bindings, case counts, gcc version, source/DLL hashes).
- **Compression is honestly red, not unresolvable.** The deflate harness
  adapts to the real generated API (3/3 harnesses) and its 10 tests fail
  against the stubs while the 19 checksum tests remain visible.
- Fuzz vectors are now persisted into spec checkpoints with oracle
  provenance tags and always regenerate when their oracle changes.

---

## Executive Summary

Alchemist successfully translated zlib (23,139 lines C → 2,512 lines Rust) with **0 unsafe blocks across 7 compiling crates**. Differential testing against C zlib then revealed that **most of the generated code is functionally non-operational** — it compiles cleanly but doesn't actually do what the C code does.

This report catalogs every bug found, defines what Alchemist needs to be a turnkey C-to-Rust system, and prioritizes the work to get there.

---

## What worked

- **Stages 1-3 produce high-quality output**: tree-sitter analysis, per-function spec extraction, architecture design with proper crate boundaries
- **Stage 4 produces compilable output**: After Phase 1 fixes (scrubber, holistic fixer, validator), 7/7 crates compile with 0 unsafe
- **Adler-32**: After fixing wrong constants, **bit-exact match with C zlib across 30,000+ random byte arrays**
- **The methodology is sound**: algorithm-first translation produces 9.2× LOC compression and clean idiomatic code
- **Local-only inference works**: Gemma 4 31B Dense at your-llm-host:8090, zero cloud cost

## What's broken (verification findings)

### Bug Class 1: Wrong constants (silent semantic errors)

**Adler-32 used BASE=255 instead of 65521.** RFC 1950 mandates 65521 (largest prime less than 2^16). The model invented constants. Spec extraction CORRECTLY identified this as RFC 1950 — Stage 4 ignored the spec.

- Found by: differential test producing different checksums
- Fix complexity: trivial (one regex)
- Severity: **CRITICAL** — would have shipped wrong cryptography

### Bug Class 2: Stub/scaffolding without real implementation

**The `compress()` function returns Ok with a zero-filled output buffer.** No DEFLATE algorithm exists. Source code literally contains comments like `// Since we don't have the actual algorithm, we use a simple heuristic` and `// for this spec, we'll assume the compression is successful`.

Found in:
- `zlib-compression/src/compress.rs` — 11 instances of "we don't have", "simulate", "for this spec"
- `zlib-compression/src/uncompr.rs` — same pattern
- `zlib-io/src/deflate.rs` — 3 `unimplemented!()` calls

The model recognized it didn't know how to implement DEFLATE/inflate but wrote stubs that compile rather than failing loudly.

- Found by: compress→uncompress roundtrip failing at C-side decompress with Z_DATA_ERROR (-3)
- Fix complexity: **HIGH** — needs real algorithm implementation
- Severity: **CRITICAL** — entire purpose of the library doesn't work

### Bug Class 3: Missing functions claimed by architecture

**No CRC-32 compute function exists in the generated Rust.** The "crc32" module in zlib-io contains only table-writing helpers (`write_crc32_table`, `byte_swap`). The actual `crc32(data: &[u8]) -> u32` doesn't exist anywhere.

Found via: searching for compute functions across all crates.
- Architecture said zlib-io would have CRC-32
- Spec extraction had `crc32_checksum` algorithm
- Implementation generated I/O helpers instead

- Fix complexity: HIGH — needs to detect and re-prompt for missing functions
- Severity: **HIGH** — algorithm declared by architecture but not implemented

### Bug Class 4: Type mismatches (z_stream vs inflate_state)

The model conflated `z_stream` (the public stream type) and `inflate_state` (internal state). Methods declared on one were called on the other. Required ~50 reactive field additions across multiple iterations.

- Found by: cargo check errors during fix loop
- Fix complexity: MEDIUM — needs upfront type schema
- Severity: MEDIUM — cascaded into many compile errors

---

## Verification findings summary

| Algorithm | Compiles | Mathematically Correct | Notes |
|-----------|----------|------------------------|-------|
| Adler-32 | ✅ | ✅ (after BASE fix) | 30K random inputs match C zlib exactly |
| CRC-32 | ✅ (helpers only) | ❌ | Compute function never generated |
| compress() | ✅ | ❌ | Returns zeros |
| uncompress() | ✅ | ❌ | Cannot decompress real DEFLATE |
| deflate (lib) | ✅ | ❌ | 18 stubs/unimplemented |
| inflate (lib) | ✅ | ❓ Untested | Likely broken given pattern |
| trees | ✅ | ❓ Untested | |
| zlib-types | ✅ | N/A | Just type defs |

**4/7 crates compile but are functionally broken.**
**1/7 crate (Adler-32) is correct after one constant fix.**
**3/7 crates (types, trees, basic structure) are at least structurally sound.**

---

## What Alchemist needs to be production-ready

### Tier 1: Mandatory for "anyone with C code can use" (estimated 6-10 weeks)

#### 1. Test-driven generation (Stage 4 must be TDD)

Currently: Stage 4 generates code → fix loop until it compiles.
Required: Stage 4 generates code → runs spec test_vectors → fix loop until tests pass.

**Implementation**:
- Every AlgorithmSpec must include test_vectors (already in schema)
- Stage 4 generates the test FIRST: `assert_eq!(adler32(b"Wikipedia"), 0x11e60398)`
- Generates the implementation
- Compiles and runs tests
- If tests fail, iterates with `cargo test` errors as feedback (not just `cargo check`)
- Refuses to mark crate "complete" until tests pass

This catches Bug Class 1 (wrong constants) at generation time. The Adler-32 BASE bug would have failed iteration 1 instead of needing manual diff testing.

#### 2. Anti-stub detection

Current scrubber catches typos. New scrubber must catch generation lies:
- `unimplemented!()` in non-test code → **REJECT GENERATION**
- `todo!()` in production code → REJECT
- Comments matching `we don't have | for this spec | conceptually | simulate` → REJECT
- Functions that take input but never use it (just return Ok) → REJECT
- Output buffers that are never written → REJECT

When detected: re-prompt with explicit instruction "implement the actual algorithm, do not stub or simulate".

#### 3. Public API completeness check

Each spec lists `source_functions: [adler32, adler32_combine]`. After Stage 4:
- Walk every source_function
- Verify a corresponding pub fn exists
- If not, RE-PROMPT for missing function with full spec context

This catches Bug Class 3 (CRC-32 missing).

#### 4. Mandatory differential testing in Stage 5

Current Stage 5 is a stub. Must become:
- Auto-generate FFI bindings for every C public function
- Auto-generate proptest harness for each
- Run 10K+ random inputs through both implementations
- Report exact matches, ULP tolerance for floats, roundtrip equivalence for compression
- **REFUSE to declare success without passing differential tests**

#### 5. Spec test-vector requirement

Stage 2 currently allows specs without test_vectors. New requirement:
- Every AlgorithmSpec MUST have ≥1 test_vector
- For algorithms referencing standards (RFC, FIPS, NIST), MUST extract test vectors from the standard
- Re-prompt extraction if missing

### Tier 2: High-value for reliability (estimated 4-6 weeks)

#### 6. Compile-driven skeleton (Phase 2 plan)

Before generating bodies, generate just types + signatures + `unimplemented!()` bodies. Verify whole workspace compiles. Only then fill bodies. Catches type-system errors (Bug Class 4) before they cascade.

#### 7. Field schema pre-scan

Already built in `architect/field_scanner.py`. Wire into pipeline so types are generated complete on first pass.

#### 8. Spec validation by second model

Have a second LLM call review each spec extraction:
- Are the constants plausible? (BASE=255 is wrong for Adler-32; reviewer would flag)
- Are the test vectors mathematically consistent?
- Cross-reference cited standards

#### 9. Context-aware fix loop

Current fix loop sees `cargo check` errors. Enhanced version sees:
- The original spec
- Cited standards (link to RFC text)
- Test vectors from the standard
- Adjacent files in the crate

When fix attempt fails, retry with HEAVIER context (full spec + standard text), then escalate to a stronger model.

### Tier 3: Polish for usability (estimated 2-4 weeks)

#### 10. Productionize CLI

Wire the validator, field scanner, holistic fixer into `alchemist translate`. Currently they're standalone scripts. Should be: `alchemist translate ./mbedtls/` and have it just work.

#### 11. Multi-codebase validation

Run on:
- mbedTLS (crypto, NIST CAVP test vectors)
- lwIP (TCP/IP, can compare against smoltcp)
- FreeRTOS (RTOS kernel)
- SQLite (boss fight)

Each surfaces new failure classes. Each becomes a generic fix.

#### 12. Plugin architecture

Domain-specific extension points:
- Crypto plugin (auto-imports test vectors, knows constant-time requirements)
- RTOS plugin (handles interrupt contexts, no_std requirements)
- Networking plugin (packet handling patterns)

---

## Estimated effort to "anyone can use it"

| Phase | Work | Time | Reliability after |
|-------|------|------|-------------------|
| Phase 1 (done) | Validator, scrubber, holistic fix | ✅ Done | ~57% crates compile |
| Phase 2 | TDD Stage 4, anti-stub, API completeness | 6-10 weeks | ~70% crates compile + correct on simple algos |
| Phase 3 | Skeleton stage, spec validation, context fix | 4-6 weeks | ~85% on standard codebases |
| Phase 4 | Multi-codebase, plugins, productionize | 4-6 weeks | Reliable for common library types |
| Phase 5 | Hard targets (kernels, drivers, generics) | 12+ weeks | Honest 50-70% on arbitrary C |

**Total: 6-9 months of focused work to reach "anyone with normal C code gets working Rust"**

For exotic C (embedded with hand-written assembly, kernel drivers, OS code), expect to never hit 100%. Those need human input on architecture.

---

## Honest current capability

If you handed Alchemist (today) to a developer and asked "translate my C library":

| C codebase profile | Current likely outcome |
|-------------------|------------------------|
| Pure stateless algorithm (single function) | High chance of compiling AND being correct |
| Algorithm library with state (zlib pattern) | Will compile, ~30-50% of functions actually work |
| Crypto library with test vectors | Will compile, semantic correctness unknown |
| Networking stack | Will compile, packet handling broken |
| Embedded RTOS | Will compile, scheduling probably non-functional |
| Kernel module | May not compile, definitely incorrect |

**Current Alchemist is a powerful research tool that proves the algorithm-first methodology works.** It's not yet a tool you'd hand to a stranger and trust the output without verification.

The PATH to that trustworthy state is clear (Tier 1 work), but it's months of work, not days.

---

## Immediate next steps (priority order)

1. **Build TDD Stage 4** (Tier 1.1) — biggest leverage, prevents most bug classes
2. **Add anti-stub scrubber rules** (Tier 1.2) — quick win, prevents silent failures
3. **Wire differential testing into pipeline** (Tier 1.4) — automates what we did manually today
4. **Apply lessons to mbedTLS** (Tier 3.11) — proves generalization

Each surfaces new requirements. Iterate.

---

## What this report proves

The verification step did its job. Without it, we would have shipped:
- Cryptographically wrong checksums
- A "compress" function that returns zeros
- A "decompress" function that cannot decompress
- A workspace that compiles but is functionally non-operational

The methodology (algorithm-first, per-file gen, scrubber, holistic fix) is real. The remaining work to make Alchemist production-grade is engineering, not research.
