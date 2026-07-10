# Conquered Translations — before/after archive

Each subdirectory holds a C→safe-Rust translation Alchemist produced **fully
autonomously** and verified **byte-exact-or-refused** against the compiled C
reference (differential gate, thousands of fuzz cases). `*.before.c/.h` is the
original C; `*.after.rs` is the generated safe Rust; `receipt.json` is the
signed verification receipt (all gates, differential result, harness config).

These are the durable proof artifacts — the box's `/tmp` working copies are
ephemeral; this archive is the record.

| Target | Domain | Before (C) | After (Rust) | Differential | Notes |
|--------|--------|-----------:|-------------:|:------------:|-------|
| **smaz** | variable-length codec | 194 LOC | 485 LOC | ✅ 2/2 @ 4000 cases | forward `goto`→goto-free, 254-entry hash codebook carried byte-exact, decoder round-trip oracle. Conquered 2026-07-10 (run9). 8 framework bugs fixed en route, zero model incapacity. |
| **sha256** | crypto digest | 4.3 KB | 28 KB | ✅ 2/2 (CAVP-backed) | NIST CAVP KAT-verified digest, cold→safe Rust. The crypto credibility milestone (Phase 2.5). |
| **lua_hash** (`luaS_hash`) | Lua string hash | 12 LOC | — | ✅ 2/2 @ 5000 cases | **FIRST Lua 5.4 function conquered** (2026-07-10). `(str,len,seed)→u32`, the hash every Lua table + string-intern depends on. Exposed + fixed 3 framework gaps: seed-as-trailing-arg checksum shape, seed missing from fill-vectors, `const char*` FFI ptr cast. Model translation was byte-identical to C throughout. |
| **lua_ceillog2** (`luaO_ceillog2`) | Lua ceil-log2 | 20 LOC | — | ✅ 1/1 differential | **2nd Lua fn** (2026-07-10). `unsigned→int` with a carried 256-byte log2 table. Exposed + fixed the Lua-typedef-carry gap (`lu_byte`→`u8`) that blocks every table-carrying Lua fn. |
| **lua_shiftl** (`luaV_shiftl`) | Lua VM int shift | 20 LOC | — | ✅ 1/1 differential | **3rd Lua fn** (2026-07-10). Pure `(i64,i64)→i64` wraparound bit-shift — the first of Lua's VM integer-overflow numerics. Exact `l_castS2U`/`l_castU2S` wrap semantics preserved. |
| **lua_hexavalue** (`luaO_hexavalue`) | Lua hex-digit parse | 6 LOC | — | ✅ 1/1 differential | **4th Lua fn** (2026-07-10). `int→int` hex-char value. Exposed + fixed two framework needs: fork-isolate the C oracle (glibc ctype UB segfault) and `ALCHEMIST_SAFE_SCALAR` bounded-domain fuzzing — which unlocks the whole ctype/char/codepoint class. |
| **lua_hash REAL-SOURCE** (`luaS_hash`) | Lua string hash | 60-file lib | — | ✅ **OVERALL PASS**, gate 5/5 differential (oracle from 32 C files) | **FIRST Lua fn conquered from the REAL whole-library source, zero hand-extraction** (2026-07-10). Scoped `lstring/luaS_hash` over all 1085 Lua fns; the pipeline built the whole-lib oracle, synthesized vectors, translated + verified byte-exact autonomously. This is what the static-exposure + LUAI_FUNC keystones unlocked — the "no test vectors" gremlin that forced hand-extraction for ~8 cycles is dead. Distinct from the earlier hand-extracted `lua_hash` row (crutch, now retired). |
| **murmur3** (4/7 fns) | non-crypto hash | 315 LOC | — | ✅ 4/7 @ 40 cases each; 3 refused | **Fresh-library TRANSFER PROBE** (2026-07-10). Never-seen hash family. `rotl32/rotl64/fmix32/fmix64` (all `static` internal fns) verified byte-exact **purely from general levers, zero bespoke work**. Surfaced + fixed 3 general levers: (1) qualifier-macro consts (`#define FORCE_INLINE inline`→bad const), (2) qualifier-macro leak into parsed return type, (3) **THE keystone — expose `static`/`inline` internal functions to the oracle** (same blocker as luaS_hash's "no test vectors"; unblocks the whole internal-function class for any real library, incl. most of Lua). The 3 `MurmurHash3_*` fns honestly **refused** (`void*` seeded-hash-to-outbuf shape not yet built) — byte-exact-or-refused holding. |

## Other verified wins (working copies on box `/tmp`, not yet archived here)
- `zlib` — deflate/inflate byte-exact round-trip, ~7.1k LOC core (Phase 2 moonshot; in `subjects/zlib-dll/`).
- `siphash`, `hashkit`, `tinychk` — see `subjects/`.
- CRC family (`c8`, `c64`, `dnp2`, `t_nmea`), `genlib` (6 reference-free fns),
  `gotolib` (WALL-3 goto proof) — box `/tmp/*/.alchemist/output`.

## What "conquered" means here
Not "compiles" and not "looks right" — **byte-for-byte identical to the C on
every fuzzed input, or the pipeline refuses to claim success.** A refusal is a
valid, honest output; a false green is the one thing the whole system exists to
prevent.
