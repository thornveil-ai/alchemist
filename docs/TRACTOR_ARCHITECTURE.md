# Alchemist — the model-agnostic verification substrate (vs TRACTOR)

**Thesis.** You don't beat TRACTOR on the model — you beat it on the substrate the
model plugs into. TRACTOR's hard problem isn't "can an LLM write Rust," it's "can
you *trust* the result at scale." Alchemist's architecture makes **verified-or-
refused hold for arbitrary C across whole codebases**, so whatever model does the
fill — Gemma today, a frontier model tomorrow — the output is provably equivalent.
The model is a swappable fill oracle in the middle; everything around it is the
durable moat.

Each pillar below is landed as a **proven, tested foundation** (end-to-end on the
box with gcc/rustc, plus unit tests).

## Pillar 1 — Effect-footprint oracle  ✅ foundation proven
Generalizes the differential from pure `input→output` to the **full observable
footprint**: captured returns ++ final bytes of every global/static. C's implicit
file-scope state maps to an explicit Rust `GlobalState` (threaded `&mut`).
*Proof:* global-state PRNG — correct Rust footprint byte-exact vs C; a one-off-by-
one constant diverges and is caught. → verified-or-refused now reaches effectful C.
*(Next increment: syscall/libc trace via LD_PRELOAD shim.)*

## Pillar 2 — Whole-program type model + bottom-up order  ✅ foundation proven
One `ProgramTypeModel` the whole program shares: every typedef/struct/pointer
resolved to ONE coherent Rust type, so a ctx produced by one fn and consumed by
another get the identical type (`SHA256_CTX*`→`&mut Sha256Ctx`, `const`→`&`).
`topo_order` gives leaves-first (recursion-tolerant) translation. → per-function
wins become codebase throughput.

## Pillar 3 — Incremental verified FFI migration  ✅ foundation proven
For a verified safe-Rust fn, emit a thin `#[no_mangle] extern "C"` wrapper: raw C
ABI (ptr+len) outside, safe core inside (raw pointers appear ONLY in the wrapper).
*Proof:* module-generated wrapper compiles as a staticlib, links into the C program
in place of the C original, whole-program output byte-identical to all-C. → migrate
one leaf at a time, prove the program is unchanged, commit, repeat. Procurement-grade.

## Pillar 4 — Coverage-driven differential  ✅ foundation proven
`measure_branch_coverage` (gcov) reports how much of the C's branch structure an
input set exercises; `boundary_inputs` probes the comparison edges C branches on.
*Proof:* branchy classifier — naive ASCII inputs 20% branch coverage, boundary-aware
100%. → "verified on N vectors" becomes "verified on coverage-complete inputs," and
the coverage number rides in the receipt.

## Pillar 5 — Verified-preserving idiomaticity  ✅ foundation proven
`verified_refactor` raises idiomaticity (iterators over raw indexing, `Result` over
sentinels) but gates EVERY candidate on the differential — byte-exact or reverted.
*Proof:* idiomatic iterator-fold refactor kept (byte-exact), `*37` breaking refactor
reverted, baseline stays correct AND idiomatic. → matches TRACTOR's idiomatic bar
without giving up equivalence.

## The pitch
Not "our model is better" — **"our harness makes any model trustworthy at codebase
scale."** The competitive edge is verification and provability, a lane TRACTOR's
scale-first framing doesn't obviously own: *a migration you can prove.*
