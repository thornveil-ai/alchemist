# `alchemist translate ./lib` — end-to-end auto-onboarding (capstone)

## What it does
Point the driver at a C file; it produces a verified Rust translation with **zero
hand-written setup**. Validated on ArduPilot's `libraries/AP_Math/crc.cpp`:

```
onboarded: 7 tables, 23 fns to fill (20 tested, 3 helpers), 240 tests
skipped (not byte-processing): crc_crc4, hash_fnv_1a, crc_crc16_ibm, crc_crc64, parity
skeleton compiles: True
after fill: 240/240
```

**240/240 differential tests byte-exact vs compiled ArduPilot C, first fill.**

## The pipeline (all derived from source)
1. `onboard.extract_tables` — every `static const` table, Rust-typed (found all 7).
2. `onboard.discover_functions` + `fill_order` — call graph, dependency order
   (fills `crc_xmodem_update` before `crc_xmodem`).
3. `oracle_gen.classify_signature` — which param is buffer / length / seed; wider
   pointers, out-pointers, and struct pointers are **skipped, not guessed** (5 of 28).
4. `oracle_gen.generate_c_harness` — compiles a dispatch oracle against the real C.
5. `auto_translate.build_crate_from_c` — emits tables + coherent-signature stubs +
   differential tests from the oracle; stubs the full call-closure of the tested set.
6. Fill each function from the C in dependency order; verify byte-exact.

## Why it matters (TRACTOR-aligned, C-first)
The hand-written `setup_*.py` scripts are gone for this function class — the
onboarding is derived, not authored. This is the core of "point it at any C and
walk away." It handled MORE than the hand-written version (20 tested fns vs 15)
because the classifier is systematic where hand-picking was partial.

## Honest scope
Covers the **byte-processing class** (buffer + length + scalars -> scalar):
checksums, hashes, codecs — the bulk of leaf C. Not yet: struct/out-pointer
signatures (flagged), stateful multi-call APIs, header/build discovery for
multi-file libraries. Those are the next rungs; the spine is proven.
