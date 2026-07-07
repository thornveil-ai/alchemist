# Tier 3 — confidence/robustness: closing the last gaps to TRACTOR parity

## #3 (the headline) Mechanical borrow-restructuring (`borrow_fix.py`)
The borrow-checker wall (E0502/E0503) is what the model kept losing to
(deflate_fast, SHA). But the errors are DETERMINISTIC — rustc names the line and
the variable — so the fix is mechanical, not a reasoning task. Two rewrites:
`f(ctx, &ctx.field)` -> hoist the borrow to a local; `x.a = f(&mut x)` -> hoist
the RHS. Applied one error at a time, recompiling between.

**Validated end-to-end:** SHA-256 filled with NO borrow hint -> the model
produced 4 E0502/E0503 conflicts -> `fix_borrows` resolved ALL of them with no
model -> byte-exact. This turns the diagnoser's job logic-only and makes borrow
restructuring a reliable pass instead of the frontier.

## #1 Fuzz depth (`gen_fuzz_lengths`)
n diverse input lengths (every boundary value, then a deterministic spread) for
deep differential fuzzing. Demonstrated: SHA-256 verified across **300 vectors**
(0..2048 bytes, block-boundary stress) in one loop test.

## #2 More signature shapes
Output-length pointer: `int f(in, inlen, out, size_t *outlen)` -> the harness
reads `*outlen` for the dump length (not the status return); Rust drops it (the
Vec length is the answer). Plus (from Tier 2) fixed-size output, array-syntax
params, typedef'd byte types, `&mut Ctx` receivers.

## Tier 3 capstone
SHA-256, no hand-written setup AND no borrow hint: onboarded -> filled ->
mechanically borrow-fixed -> 300-vector deep fuzz -> byte-exact vs compiled C.

## Honest remaining edge
The deepest fuzz layer — coverage-guided (cargo-fuzz/libFuzzer with a differential
target that explores) — is the next depth beyond embedded vectors. And borrow_fix
covers the two dominant patterns; exotic aliasing (returning a reference across a
mutation, self-referential structs) still falls back to the diagnoser. But the
frontier that actually blocked progress — routine E0502/E0503 restructuring — is
now mechanical.
