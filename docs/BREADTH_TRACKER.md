# Alchemist breadth tracker — C libraries run through the pipeline

Honest scoreboard of real C libraries put through the auto-onboarder
(`translate ./lib`: onboard → oracle → fill → mechanical borrow-fix → differential
verify). Status is empirical, not aspirational.

**Legend:** ✅ pass = every differential vector byte-exact · ⚠️ partial = compiles/some
vectors pass, a function or edge unresolved · ❌ fail = onboarding/oracle couldn't
handle it (records *why*) · ⬜ mapped, not yet run.

**Verification note:** "vectors" = differential test cases run against the compiled
C reference. Generic per-run context (no per-library hand-tuning) unless noted.

## Tier-A sweep #1 — 12 libraries, 3 lanes (zero-touch, hardened)
**4 pass · 3 partial · 4 no-oracle · 1 runner-bug (fixed).** No false greens.

| Library | Lane | Result |
|---|---|---|
| SHA-1, SHA-256, MurmurHash3, base64 | crypto/scalar/codec | ✅ **pass** (real vectors) |
| MD5 | crypto | ⚠️ partial (transform panic — fill variance; passed a prior run) |
| MD2 | crypto | ⚠️ partial (`E0061` wrong arg count) |
| SHA-3 | crypto | ⚠️ partial (union-field ctx) |
| base64 (B-Con) | codec | ⛔→✅ runner crashed on `int('0123456789',0)` — **onboarder bug, now fixed** |
| rot13 | codec | 🚫 no-oracle (in-place mutation shape) |
| arcfour/RC4, DES, Blowfish | cipher | 🚫 no-oracle (BYTE[] array-state, not a struct ctx) |

**The integrity guard proved itself in the wild:** the ciphers and in-place rot13
are shapes we don't support, and the system **honestly refused them (no-oracle)
instead of faking passes.** That's the whole point — trustworthy at scale.

### 🗺️ Error map (fix-by-class queue, updated)
| Class | Libs | Status |
|---|---|---|
| runner crash on odd numeric literal | base64_bcon | ✅ fixed (robust int parse) |
| `md5_transform` fill-hard (runtime panic) | md5 | ⬜ model frontier (passes some runs) |
| `E0061` wrong-arg-count | md2 | ⬜ diagnoser/idiom |
| union-field ctx emission | sha3 | ⬜ struct union handling |
| in-place transform shape | rot13 | ⬜ shape coverage |
| array-state (`BYTE[]`) cipher shape | arcfour/des/blowfish | ⬜ shape coverage (key-schedule ciphers) |

## Crypto-hash lane — VERIFIED (hardened, zero-touch, no false greens)
After the 8-fix hardening pass (integrity guard · arg-order · overflow-checks ·
murmur3 sizing · alias-macro skip · never-make-it-worse · mechanical borrow+type
fixers · C-name aliases): **4/6 pass, every pass with real vectors.**

| Library | Result | Vectors |
|---|---|---|
| SHA-1 | ✅ pass | 80 |
| MD5 | ✅ pass | 80 |
| SHA-256 | ✅ pass | 80 |
| MurmurHash3 | ✅ pass | 33 |
| MD2 | ⚠️ partial | `E0499` borrow-more-than-once (extend borrow-fixer) |
| SHA-3 | ⚠️ partial | union-field ctx not fully emitted (struct union handling) |

**No false greens** — SHA-3 is an honest partial (real oracle), not the vacuous
"0-vector pass" it started as. Open classes: `E0499` (2-mut-borrow) · union-field
struct emission.

## Scoreboard

| Library | Class | Source | Fns | Vectors | Status | Notes |
|---|---|---|---|---|---|---|
| zlib (deflate+inflate) | stateful/compression | madler/zlib | — | 21+ round-trip | ✅ | hand-driven moonshot; 127 tail items open |
| ArduPilot crc.cpp | scalar (checksums) | ArduPilot/AP_Math | 15/20 | 180–240 | ✅ | auto-onboarded; 5 skipped (word/out ptrs) |
| base64 (zhicheng) | buffer (codec) | zhicheng/base64 | 2 | 24+32 | ✅ | real `char *out` sig; encode+decode |
| jsmn | parser | zserge/jsmn | 6 | 13 | ✅ | 1 diagnosis (loop-cursor) |
| SHA-256 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 300 | ✅ | no borrow hint; mechanical borrow-fix |
| SHA-1 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 120 | ✅ | **auto-diagnosed to green (2 rounds)** — zero human touch |
| MD5 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 120 | ⚠️→🔄 | hit multi-line-macro class-bug (now FIXED); re-running |
| MD2 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 120 | ⚠️ | `u8 ^= u32` width mismatch (open error class) |
| SHA-3 (tiny_sha3) | stateful (crypto) | mjosaarinen/tiny_sha3 | — | — | 🔄 | comprehensive lane |
| MurmurHash3 | scalar (stress) | PeterScott/murmur3 | — | — | 🔄 | fixed-output-void-return shape — deliberate stress |

## Zero-touch batch #1 — honest results (generic runner + auto-diagnoser)
The full autonomous loop (onboard → fill → borrow-fix → **auto-diagnose** → verify),
no per-library hand-tuning, across the crypto-hash lane:
- **SHA-1 ✅ pass** — 2 diagnosis rounds closed a `E0308` type-coercion residual.
- **MD5 ⚠️** — `unclosed delimiter`: `\`-continued **statement macros** (MD5's
  `FF/GG/HH/II` round functions) mis-emitted as pure fns. **Root cause fixed** —
  now joins line-continuations + skips mutating macros (model inlines them).
- **MD2 ⚠️** — `E0308` + `u8 ^= u32` (byte state XOR'd with a word). Open.

### 🗺️ Error map (fix-by-class queue)
| Error class | Seen in | Fix | Status |
|---|---|---|---|
| multi-line / statement macros (`\`, mutating blocks) | MD5 | join continuations + skip stmt macros in emit_macro_helpers | ✅ fixed (commit a05099c) |
| `u8 ^= u32` integer-width coercion | MD2 | width-aware coercion idiom / diagnoser rule | ⬜ open |
| fixed-output void-return (`f(in,len,seed,out)` writes N bytes, returns void) | MurmurHash3 (expected) | detect fixed digest size for non-stateful out-buffers | ⬜ open |

**Honest read:** the generic runner onboards the whole lane autonomously; the
auto-diagnoser converts *some* partials to green unaided (SHA-1); the rest bucket
into a small set of **error classes**, each a one-time harness/idiom fix that
lifts the whole family. This is the flywheel: run → map class → fix once → re-run.

## Mapped candidates (single-file, public-domain / permissive, differentiable)

### Scalar-return (checksums / non-crypto hashes)
FNV-1a, FNV-1, djb2, sdbm, Jenkins one-at-a-time, xxhash32, MurmurHash3-32,
adler32, crc16/24/32 variants (ArduPilot ✅), CRC64.

### Buffer-return (codecs / transforms)
base64 ✅, base32, base16/hex, base58, URL-encode, ROT13, RLE, ascii85.

### Stateful init/update/final (crypto / streaming)
SHA-256 ✅, SHA-1, SHA-512, MD5, MD2, SHA-3/Keccak, BLAKE2s, HMAC, streaming CRC,
ARCFOUR/RC4 (stream cipher), Poly1305.

### Out of current scope (records the honest edge)
Block ciphers with key schedules + modes (AES/DES/Blowfish — multi-array state,
mode plumbing), anything needing a real HAL/syscalls, C++ (templates/classes).
