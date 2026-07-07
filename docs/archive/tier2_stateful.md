# Tier 2 — coverage: stateful APIs, new signature shapes, fuzz depth

One target hit all three Tier 2 items: **SHA-256** (Brad Conte, public domain) —
stateful crypto, exactly TRACTOR's domain.

## Result
`build_stateful_crate` onboarded sha256.c/.h with no hand-written setup, the model
filled all four functions from the C, and the deep fuzz test passed:

```
detected API: init=sha256_init update=sha256_update final=sha256_final
              helpers=[sha256_transform] digest_len=32
fill order: [sha256_transform, sha256_init, sha256_update, sha256_final]
fuzz vectors: 68   (lengths 0..1025, block-boundary stress)
fuzz_autosha ... ok   # byte-exact vs compiled C SHA-256 on every vector
```

## #1 Stateful struct APIs (`stateful.py`)
Detect the ctx struct (most-common first-pointer-param type) + the init/update/final
trio by name+signature; emit the Rust ctx struct from the header (fixed C arrays ->
Rust arrays, manual Default for arrays > 32); drive a SEQUENCE oracle
(init -> update(data) -> final(digest)). Function-like C macros (ROTRIGHT/CH/MAJ/
SIG0...) are emitted as Rust helper fns keeping their C names (rotations ->
rotate_left/right, avoiding shift-by-width panics).

## #2 New signature shapes
`&mut Ctx` state receivers; a fixed-size output buffer (digest length from a
`*_SIZE` #define); array-syntax params (`const BYTE data[]` -> `&[u8]`); typedef'd
byte types (BYTE/WORD resolved before classification).

## #3 Fuzz-depth verification
68 deterministic vectors spanning block boundaries, embedded as one data-driven
loop test — real coverage, not ~12 hand cases.

## Honest note
Structure/detection/oracle/fuzz are fully autonomous. The fill needed one general
coherent-model rule made explicit — the borrow-split for `f(&mut ctx, &ctx.field)`
(copy the Copy field to a local first). That's a cataloged idiom, not a per-case
hack; the model applies the simple idioms but borrow *restructuring* still benefits
from the explicit rule (same frontier as deflate_fast).
