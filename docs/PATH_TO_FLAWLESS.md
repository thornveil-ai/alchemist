# The Path to "Flawless"

**Status:** design doc / assurance roadmap. Companion to
[`ROADMAP.md`](../ROADMAP.md) (schedule) and
[`PRODUCTION_READINESS.md`](../PRODUCTION_READINESS.md) (current honest state).
**Last reviewed:** 2026-07-03

---

## What "flawless" is allowed to mean

"Flawlessly converts C applications to Rust" is not a claim any tool can make
over arbitrary C, for reasons that are mathematical, not engineering:

- **C programs don't have one behavior.** Undefined behavior, unspecified
  evaluation order, and `#ifdef` configuration explosion mean "equivalent to
  the C" is ill-posed until you pin *which* C — a specific source
  configuration compiled by a specific toolchain. (This repo has already paid
  this tax once: zlib's CRC braid has W=4 and W=8 variants, and three
  different pieces of this codebase disagreed about which one was "the"
  algorithm. See the 2026-07-03 addendum in PRODUCTION_READINESS.md.)
- **Equivalence of arbitrary programs is undecidable.** Any general claim is
  bounded: bounded inputs, bounded iterations, stated equivalence relation.
- **Some C behavior has no Rust meaning by design** — data races, pointer
  provenance games, `longjmp` across frames.

So the summit this project can actually stand on is:

> **Flawless-or-refused.** Every function Alchemist emits carries a
> machine-checkable equivalence claim at a stated assurance level, against a
> pinned C reference artifact, with a signed receipt. Anything it cannot
> verify to the configured threshold, it refuses to emit. The tool's failure
> budget is *refusals*, never *silent wrongness* — and the refusal rate is
> the number we drive toward zero.

That is the honest form of "flawless": **zero unverified claims**, not zero
defects in the universe. Everything below is the ladder to that claim.

---

## The assurance ladder

Every emitted function gets stamped with the highest level it has passed.
A workspace-level claim is only as strong as its weakest public function.

| Level | Claim | Mechanism | Status (zlib subject) |
|-------|-------|-----------|----------------------|
| **L0** | compiles, `#![forbid(unsafe_code)]` | cargo + no-unsafe gate | all crates |
| **L1** | not a stub, right algorithm *shape* | anti-stub + semantic lints | all crates (semantic gate live 2026-07-03) |
| **L2** | matches published standards vectors | RFC/NIST fixed vectors | adler32, crc32 |
| **L3** | matches compiled C on randomized + boundary inputs | automated differential oracle (adapter_gen) + shim FFI for statics + fold-edge boundary tests | adler32_z, crc32 — 5000 cases + boundary lengths each; crc_word, crc_word_big, multmodp, x2nmodp via checksum-shim vectors |
| **L4** | matches compiled C under coverage-guided fuzzing, UB-screened | branch-coverage-driven differential fuzzing; sanitized C oracle | — not built |
| **L5** | proven equivalent within stated bounds | paired bounded model checking / symbolic equivalence | — not built |
| **L6** | compositional proof across call graph | function contracts + whole-crate composition | — research |

**Status 2026-07-03 (second pass):** zlib-checksum is the first crate green
through ALL six gates (`OVERALL: PASS`, receipted) — table-generation
functions are hardported and anchored byte-for-byte against zlib's shipped
`crc32.h`/`inffixed.h`. Receipts (G7-lite), oracle-tagged vector persistence
(G4-lite), the checksum shim oracle with fail-closed cross-check (G1 for
statics), full-footprint compression adapters (G2), and boundary-length
differentials (G3-lite) are live. "Contract-ready" (per ROADMAP) is L3–L4
across a whole library's public API. "Flawless-or-refused" is L4 default,
L5 for the functions that matter, refusal below threshold.

---

## The gap program

In dependency order. G1–G4 harden the *oracle and evidence*; G5 grows the
*generation* capability the evidence measures; G6–G7 turn evidence into
*proof and receipts*; G8 scales it.

### G1. Oracle integrity — never verify against a derivation
The crc_word_big failure was not a translation bug first; it was an **oracle
bug**: the pure-Python reference implemented a variant that matches no real
zlib build, and the tests it generated blessed wrong code. Rules going
forward:

- **The oracle is the compiled artifact.** `local`/static C functions get
  shim-exported (extend the existing `subjects/zlib/shim/` pattern) so every
  function has an FFI oracle. Pure-Python references are allowed only as
  cross-checks, never as sole ground truth, and must be anchored to shipped
  artifacts (as the corrected CRC table now anchors to zlib's `crc32.h`).
- **Pin the configuration.** The verification receipt records the C
  toolchain, flags, and the `#define` set of the reference build. Where a
  subject has behavior-relevant config variants (W=4/W=8), either enumerate
  and verify per-variant or document the pinned choice.
- **Screen the oracle for UB.** Build the reference DLL with UBSan/ASan for
  fuzzing runs. An input that triggers UB in the C is excluded from the
  equivalence corpus and logged as a *documented divergence* — the Rust is
  allowed (encouraged) to differ from undefined behavior.

### G2. Full effect-footprint comparison for every category
Checksums verify on return values. Everything else mutates: out-params,
buffers, stream state, error codes. The adapter layer (adapter_gen) must grow
templates that capture and compare the **whole footprint** — `(status,
out_buffers, mutated_state)` tuples on both sides — for:

- compression/decompression (roundtrip + C↔Rust interop + rc comparison,
  no asserts inside wrappers that hide status divergence),
- ciphers (encrypt/decrypt/interop, CAVP vectors),
- streaming/stateful APIs (init → update* → finish sequences driven by a
  script generated from the spec's state machine).

Unadaptable shapes keep failing closed (per-algorithm `ADAPTER UNRESOLVED`
tests, as shipped 2026-07-03).

### G3. Coverage-guided differential fuzzing (L3 → L4)
Random bytes plateau fast. L4 requires:

- a shared corpus driven by branch coverage measured on **both** sides
  (C via gcov/LLVM cov on the DLL build; Rust via `cargo-fuzz`/llvm-cov),
- structured generators per input grammar (valid/corrupted DEFLATE streams,
  not just byte soup),
- boundary-value injection derived from the spec's constants (NMAX block
  edges, Z_BATCH thresholds, 0/1/len-1/len/usize-boundary sizes),
- a stopping criterion that is a *coverage number in the receipt*, not a
  case count.

### G4. Tear down the spec wall
All correctness flows through AlgorithmSpec, and the live extraction path
still leaves `invariants` and `test_vectors` mostly empty. Required:

- extraction must populate invariants + vectors on the live path (fuzz
  backfill persisted into the spec checkpoint, not regenerated ephemerally),
- standards vectors imported from the catalog *independently* of the model
  (never derived from the code under test — same correlation rule as G1),
- two-model spec cross-examination (ROADMAP M12) so "the model invented a
  constant" dies at extract time.

### G5. Generation has to catch up with verification
An assurance ladder over stubs is a ladder over nothing. The flagship gaps:

- implement the 6 remaining zlib-checksum table-generation skeletons (clears
  the crate's anti-stub gate → first fully-green crate),
- the inflate/deflate state machine (goto→enum translation — the moonshot;
  unblocks L2–L4 for the compression crates),
- whole-workspace type coherence so cross-crate state types stop drifting.

This tranche needs the local model (Gemma 4 31B via vLLM) live; the gates
built so far are exactly what keeps that model honest when it returns.

### G6. From evidence to proof (L5)
The word "flawless" earns quotation-mark removal only here:

- **Rust-side absence proofs first** (cheapest wins): panic-freedom,
  overflow-freedom, slice-bounds safety on emitted functions via Kani or
  Prusti harnesses generated from the spec.
- **Paired bounded equivalence:** auto-generate matched harnesses — CBMC on
  the C function, Kani on the Rust — proving byte-equality of the effect
  footprint for all inputs up to a stated bound (e.g., buffers ≤ N bytes,
  loop unwinding ≤ k). The bound goes in the receipt.
- **Symbolic equivalence for leaf functions:** SAW-style LLVM-vs-MIR
  equivalence checking for pure leaves (checksums, table lookups, bit math).
  This is the same class of machinery AWS uses to verify libcrypto — mature
  for exactly the function shapes Alchemist emits first.
- **A formal equivalence relation, written down:** effect footprint
  definition, float ULP policy, UB carve-outs (per G1), allowed error-path
  divergences. The relation is part of the public methodology paper (M16).

### G7. Receipts — the claim becomes an artifact
Every emitted function ships with a machine-readable verification
certificate: assurance level, oracle identity (toolchain + flags + source
hash), case counts, coverage numbers, proof bounds, divergence log. The
workspace report aggregates them; `alchemist translate` exit status is
computed *from the receipts*, and the receipts are content-addressed and
**signed** (signet integration — Apache-2.0, already on PyPI as
`signet-sign`) so a downstream consumer can verify the claim chain without
re-running anything. "Trust me" becomes "check the signature."

### G8. The scale ladder
tinychk → zlib → mbedTLS (NIST CAVP) → lwIP → SQLite, per ROADMAP M09–M20.
The rule that makes scaling meaningful: **a new subject may add refusals,
never unverified emissions.** Refusal-rate-per-subject becomes the public
metric — the number that trends toward zero across releases while the claim
discipline stays fixed.

---

## Permanently outside the claim

Stated once, so nobody discovers them in a dispute:

- **UB-dependent behavior** — verified against the pinned compiled artifact;
  UB-triggering inputs are documented divergences, not equivalence targets.
- **Data races / weak-memory behavior** — C races have no defined behavior to
  be equivalent to; concurrent code is translated against its locked
  semantics or refused.
- **Timing and side channels** — functional equivalence only, unless a
  constant-time plugin (crypto) adds that check explicitly.
- **Bit-identical floating point across optimization levels** — ULP-bounded
  per the stated policy, not bit-fetish.
- **I/O interleaving beyond the libc contract.**

---

## Sequencing against the ROADMAP

| Tranche | Gaps | Rides with | Realistic scale |
|---------|------|-----------|-----------------|
| Evidence hardening | G1, G2, G4 | M03–M09 (Tier 1, 90-day window) | weeks each |
| Fuzzing to L4 | G3 | M10–M13 (zlib e2e) | ~a quarter |
| Generation catch-up | G5 | M13 (zlib e2e verified) | model-gated; the moonshot |
| Proof layer to L5 | G6 | M14–M20, paper M16 | quarters, research-grade |
| Receipts + signing | G7 | M19 productization | weeks once formats settle |
| Scale ladder | G8 | M20–M24 | ongoing |

The first public sentence this path is building toward, printable in the
README without violating the project's own ethos:

> *On the validated subjects, 100% of emitted public functions are verified
> equivalent to the pinned C reference at L4 or better, with signed
> receipts; everything else was refused. Refusal rate this release: N%.*

When N is small and the subject list is long, that sentence **is** "flawless"
— stated in a form that survives an audit.
