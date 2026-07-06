# Alchemist breadth tracker — C libraries run through the pipeline

Honest scoreboard of real C libraries put through the auto-onboarder
(`translate ./lib`: onboard → oracle → fill → mechanical borrow-fix → differential
verify). Status is empirical, not aspirational.

**Legend:** ✅ pass = every differential vector byte-exact · ⚠️ partial = compiles/some
vectors pass, a function or edge unresolved · ❌ fail = onboarding/oracle couldn't
handle it (records *why*) · ⬜ mapped, not yet run.

**Verification note:** "vectors" = differential test cases run against the compiled
C reference. Generic per-run context (no per-library hand-tuning) unless noted.

## Scoreboard

| Library | Class | Source | Fns | Vectors | Status | Notes |
|---|---|---|---|---|---|---|
| zlib (deflate+inflate) | stateful/compression | madler/zlib | — | 21+ round-trip | ✅ | hand-driven moonshot; 127 tail items open |
| ArduPilot crc.cpp | scalar (checksums) | ArduPilot/AP_Math | 15/20 | 180–240 | ✅ | auto-onboarded; 5 skipped (word/out ptrs) |
| base64 (zhicheng) | buffer (codec) | zhicheng/base64 | 2 | 24+32 | ✅ | real `char *out` sig; encode+decode |
| jsmn | parser | zserge/jsmn | 6 | 13 | ✅ | 1 diagnosis (loop-cursor) |
| SHA-256 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 300 | ✅ | no borrow hint; mechanical borrow-fix |
| SHA-1 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 120 | ⚠️ | auto-onboarded + filled + compiled; residual `E0308 mismatched types` (u32/i32 coercion) — one diagnosis away |
| MD5 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 120 | 🔄 | generic-runner batch |
| MD2 | stateful (crypto) | B-Con/crypto-algorithms | 4 | 120 | 🔄 | generic-runner batch |

**Batch note (honest):** the generic runner (no per-library hand-tuning) onboards
every crypto hash cleanly — API detection, ctx struct, macros, oracle, fuzz all
autonomous. SHA-1's fill compiled but left a type-coercion mismatch; that's the
*generic-context* tax (SHA-256 needed a targeted state-word hint). Per-library
convergence is a diagnosis loop, not a wall — recording raw generic-run results
here to be honest about where a zero-touch run lands vs a guided one.

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
