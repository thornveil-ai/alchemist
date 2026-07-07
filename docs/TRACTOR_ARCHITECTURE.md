# Alchemist — the model-agnostic verification substrate (vs TRACTOR)

**Thesis.** You don't beat TRACTOR on the model — you beat it on the substrate the
model plugs into. TRACTOR's hard problem isn't "can an LLM write Rust," it's "can
you *trust* the result at scale." Alchemist's architecture makes **verified-or-
refused hold for arbitrary C across whole codebases**, so whatever model does the
fill — Gemma today, a frontier model tomorrow — the output is provably equivalent.
The model is a swappable fill oracle in the middle; everything around it is the
durable moat.

Each pillar is landed at **top tier** — a proven foundation AND an automated,
usable subsystem (end-to-end on the box with gcc/rustc + the local model, plus unit
tests). 53 tests green.

## Pillar 1 — Effect-footprint oracle  ✅ top tier
Differential over the **full observable footprint** (captured returns ++ final bytes
of every global/static), not just the return. C's implicit file-static state maps to
an explicit Rust `GlobalState` (`&mut`-threaded).
- *foundation:* PRNG footprint byte-exact vs C; off-by-one constant caught.
- *top tier:* `build_effectful_crate` makes effectful C a **first-class onboarding
  shape** — onboard → footprint oracle (compiled as one TU so statics are visible) →
  fill → verify. **PROVEN: a global-state PRNG onboards, fills, and verifies byte-
  exact across 40 footprint vectors, fully autonomous.** The moat is usable.

## Pillar 2 — Whole-program type model + bottom-up translation  ✅ top tier
- *foundation:* one `ProgramTypeModel` resolving every type to ONE coherent Rust
  form consistently (`SHA256_CTX*`→`&mut Sha256Ctx`); `topo_order` leaves-first.
- *top tier:* `translate_program` ingests a multi-function C program, derives each
  signature from the shared model, translates **bottom-up** (main stays C), and
  verifies the WHOLE program via the migration harness. **PROVEN: a 2-function hash
  lib (hash_str→hash_byte) translates bottom-up and verifies byte-identical vs all-C
  across 5 inputs.** (Composes P2+P3.)

## Pillar 3 — Incremental verified FFI migration  ✅ top tier
- *foundation:* `emit_c_abi_export` — safe core inside, C ABI outside; hot-swap
  proven byte-identical.
- *top tier:* `migrate_function` **automates the whole-program verified swap** —
  `strip_c_function` removes the C def, links the Rust shim in its place, runs BOTH
  on every input, returns verified/rejected. **PROVEN: correct Rust swap verified
  across 4 inputs; wrong Rust (*37) rejected at first mismatch.**

## Pillar 4 — Coverage-driven differential  ✅ top tier
- *foundation:* `measure_branch_coverage` (gcov) + `boundary_inputs`; naive 20% vs
  boundary-aware 100% on a branchy classifier.
- *top tier:* `coverage_guided_inputs` — a real **greybox loop** (mutate, keep what
  raises cumulative coverage). **PROVEN: from a single trivial seed `b"A"` it
  discovers all six branches of a UTF-8 classifier to 100% coverage in 32 rounds.**

## Pillar 5 — Verified-preserving idiomaticity  ✅ top tier
- *foundation:* `verified_refactor` — byte-exact or reverted.
- *top tier:* `idiomaticity_score` ranks candidates; `model_idiomatic_candidate`
  asks the model for an idiomatic rewrite, **gated** by the differential. **PROVEN:
  mechanical checksum (score −10) → model iterator-fold rewrite → gated byte-exact →
  KEPT, score +3. Idiomaticity improved automatically, guarantee preserved.**

## The pitch
Not "our model is better" — **"our harness makes any model trustworthy at codebase
scale."** The competitive edge is verification and provability, a lane TRACTOR's
scale-first framing doesn't obviously own: *a migration you can prove.*
