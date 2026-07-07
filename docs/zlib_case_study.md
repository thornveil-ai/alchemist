# Case study: byte-exact zlib in safe Rust

> **The headline:** Alchemist translated **zlib** — compressor *and* decompressor — from C into pure safe Rust, and proved it with a **byte-exact full round-trip**: `Rust deflate → Rust inflate → the original bytes`, identical to the reference C library across compression levels 1–9 and every input shape tested.

This is the flagship proof that the differential-oracle method carries genuinely hard C — not a toy — into correct Rust.

---

## Why zlib is a real test, not a toy

zlib has essentially every construct that makes C painful to translate correctly:

| Hard thing | Where it shows up |
|---|---|
| A ~30-state decode machine | the `inflate()` driver |
| `goto`-based control flow | `goto inf_leave` on every input-underflow |
| `union` fields | `ct_data.fc` (freq/code), `.dl` (dad/len) |
| Pointer aliasing | `s->dyn_ltree` and `l_desc.dyn_tree` are the *same memory* |
| Bit-level manipulation | the Huffman coder/decoder, the bit accumulator |
| Macro-heavy code | `NEEDBITS`/`DROPBITS`/`INSERT_STRING`/`FLUSH_BLOCK` |
| Cross-buffer copies | stored blocks, the sliding window, LZ77 back-references |
| Pointer-into-array offsets | `lencode`/`distcode`/`next` into the shared `codes[]` table |

Each of these had to be re-expressed in safe Rust's ownership model — no `unsafe`, no raw pointers — and still produce the **identical bit stream**.

---

## What was verified (all byte-exact vs the reference C library)

**Compression (`deflate`):**
- Levels **1–9** (greedy `deflate_fast` L1–3, lazy `deflate_slow` L4–9) — 43 end-to-end cases
- `Z_HUFFMAN_ONLY` strategy — 26 cases
- `Z_RLE` strategy — 8 cases

**Decompression (`inflate`):**
- Raw **stored** streams — 5 cases
- **Dynamic** and **fixed** Huffman streams (with LZ77 matches) — 10 cases

**Full round-trip (`Rust deflate → Rust inflate → original`):**
- **21/21** across levels 1/6/9 × {empty, single-byte, text, repetitive, random, low-alphabet, periodic}

Every check is byte-for-byte against the real zlib (via its Python binding, which *is* the C library). No "looks right." No sampling that could miss a corner.

---

## The part that matters most: the oracle caught real bugs

A plausible-looking translation that passes unit tests can still be wrong. The value of the **differential oracle** — comparing against the real C on real data, end to end — is that it *finds the wrongness*. During this translation it caught roughly **nine** integration bugs that every isolated per-function test had passed clean over, including:

1. **`init_block` wiped the entire state** (`*s = DeflateState::default()`) instead of only zeroing tree frequencies — invisible to unit tests that only checked the frequencies afterward.
2. **`detect_data_type` had a `1 << i` overflow** for `i ≥ 32` — its own tests happened to hit an early return before reaching it.
3. **`scan_tree` was missing the initial `max_count = 138`** before its loop, so the first zero-run capped at 7 and emitted a spurious repeat code — only visible on real trees with long zero runs.
4. **The C aliasing gap**: `build_tree` operated on `desc.dyn_tree` while frequencies lived in `s.dyn_ltree` — the same memory in C, separate `Vec`s in Rust. Caught because the compressed block came out the wrong *type* (static where C chose dynamic).
5. **`deflate_slow` kept stale local copies** of `strstart`/`lookahead` that `fill_window` had since mutated — surfaced as an underflow on real input.
6. **`inflate_fixed`'s distance table needed 32 length-5 codes**, not 30, to be a complete Huffman code — caught as a decode failure on the first fixed block.

None of these are exotic. They're exactly the kind of subtle, integration-level mistakes that "compiles and passes tests" hides — and exactly what byte-exact-or-refused is designed to expose.

---

## Honest limitations

This is a real result, stated honestly:

- **Semi-automated, human-in-the-loop.** The method drove the translation, but a human designed the differential oracles, made coherent-model decisions (how to represent drained input `Vec`s, the shared `codes` table as offsets, the pointer-aliasing bridge), and hand-wrote the `inflate()` driver's control-flow skeleton (the `goto`→labeled-break) that the model could not.
- **The oracle must be buildable.** You need a way to run the C reference to compare against. Libraries with hardware/OS dependencies, non-determinism, or no compilable reference are harder to oracle.
- **A few per-case modeling decisions remain** (e.g. `deflate_stored`'s reach-backward into already-consumed input is a coherent-model choice, deferred).
- **Scale is unproven** beyond zlib's few-thousand lines. "Millions of lines, fully automatic" is the roadmap, not today's reality.

### Surface completion (2026-07-07 — the public API is now filled)

The compressor and decompressor round-trip byte-exact, and the remaining public API
surface has since been completed and differentially verified:

- **`deflate_stored` (level 0)** — DONE, byte-exact vs C zlib across all block
  boundaries (empty, 65534/65535/65536, and multi-block 131070–200000-byte inputs).
- **`compress`/`uncompress` wrappers** (all 7 `_z`/non-`_z` variants) — DONE, compress↔
  uncompress round-trip proven.
- **`compress_bound`, `zlib_compile_flags`, the `_`-init variants, `inflate_prime`,
  `deflate_get_dictionary`** — DONE (note: 20 `compress_bound` KAT tests were found to
  disagree with real C and were regenerated from the C reference — a test-gen bug fixed).
- **`inflate_fast`, `inflate_back`** — intentionally OMITTED in this *safe* port.
  `inflate_fast` is zlib's unchecked-pointer decode optimization (no safe-Rust
  equivalent, and the safe slow path is already byte-exact); `inflate_back`'s port
  signature is a non-functional placeholder with zero callers. Both are documented,
  non-panicking omissions rather than `unsafe` reimplementations.

Result: **zero `unimplemented!()` in the workspace, 454 tests green, byte-exact vs C at
levels 0–9.** Still open: gzip wrapper (`wbits +16`) and incremental multi-call
`avail_in`/`avail_out` streaming (whole-buffer calls are verified).

## The takeaway

The thesis — *differential oracles can drive correct C→Rust on the hardest constructs* — is proven end to end. You get a **correctness guarantee** (byte-exact or the pipeline refuses), on code that has state machines, aliasing, `goto`, unions, and bit-twiddling. That guarantee is the durable asset. The next mountain is making it flawless *and* fully automatic on arbitrary libraries.
