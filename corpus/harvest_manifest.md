# Alchemist volume harvest manifest — prioritized by VERIFY RATE

Goal: thousands of oracle-verified (C→Rust) pairs for the distillation corpus.
Ordered by expected pass-rate on a fast local model (Gemma-4-26B-A4B), because
volume = source_functions × verify_rate. Crypto PERMUTATIONS are deliberately
LOW priority — TinyJAMBU (NLFSR) verified but Sparkle (ARX) refused on all 3
models, so ARX/complex perms are model-hard, not easy volume.

Each entry: source (permissive license), ~function count, oracle shape, prep.

## TIER 1 — highest verify rate (scalar / checksum / seeded-hash shapes; proven)
These are the reliable pair factories. Expect 70-95% verify on the fast model.

- **CRC catalog** — pycrc-generated or Greg Cook catalog. crc8/16/32/64 ×
  many polynomials (CCITT, XMODEM, KERMIT, DNP, MODBUS, etc.). ~40-80 fns.
  Shape: checksum/scalar. Prep: one crc_variants.c per family. HUGE yield.
- **Non-crypto hash family** — FNV-1/1a (32/64), djb2, sdbm, Jenkins one-at-a-time,
  Pearson, ELF hash, Bernstein. ~15-25 fns. Shape: scalar/seeded. Prep: hashes.c.
- **Checksum family** — Adler-32, Fletcher-16/32/64, Internet checksum (RFC1071),
  BSD sum, SysV sum, Luhn, Verhoeff, Damm, ISBN/EAN check digits. ~15-25 fns.
  Shape: checksum/scalar. (fletcher4 already done — do the rest.)
- **Full libfixmath integer set** — the ~25 fns beyond the 15 we did:
  fix16_min/max/clamp/abs, fix16_sq, fix16_from/to_int variants, saturating +
  the q16 utility fns. Shape: scalar. Prep: full fix16.c (already staged).
- **Integer bit-twiddling** — popcount, clz/ctz wrappers, parity, bit-reverse,
  next-pow2, isqrt, ilog2, gcd, lcm, isprime(small). ~15 fns. Shape: scalar.

## TIER 2 — good verify rate (buf_transform / ctx_transform; proven on TinyJAMBU/hashes)
- **Simple block/stream primitives** — TEA/XTEA/XXTEA encrypt/decrypt (tiny, ARX
  but SMALL), RC4 ksa/prga (done), ChaCha quarter-round, Salsa20 core.
  Shape: buf_transform. Mixed yield (small ARX ok, big ARX hard).
- **Byte codecs** — base64 enc/dec (done), base32, base16/hex, base58, ascii85,
  URL-encode, quoted-printable, COBS encode/decode. Shape: cstr/buf_transform.
- **LEB128 / varint** — encode/decode (protobuf-style). Shape: buf_transform.
- **Simple hash cores** — MD5/SHA1/SHA256 transform (sha256 done), FNV, xxhash32.
  Shape: ctx_transform/digest.

## TIER 3 — model-hard (route to frontier teacher, harvest as HARD examples)
- **Crypto ARX permutations** — Sparkle, Xoodoo, Gimli, Chaskey. (Sparkle refused
  ×3 models.) These are the distillation TARGET class, not easy volume.
- **Bit-serial arithmetic** — fix16_div/sdiv, long division, fixed-point
  transcendentals (exp/log/trig/atan2). div-class. Frontier teacher.

## TIER 4 — needs ORACLE-SHAPE expansion (not model, not frontier)
- Parsers (jsmn, parson DOM, http_parser), state machines, allocators.
  These refuse "no verifiable test vectors" — separate oracle-coverage track.

## Execution
1. Prep Tier-1 subjects (one .c dir each) → `subjects/harvest/<name>/`.
2. `python tools/batch_run.py --glob 'subjects/harvest/*'` with Gemma-4-26B-A4B
   on :8086 → pairs.jsonl grows, escalation_queue classes model_hard vs oracle_gap.
3. Tier-3 model_hard queue → gpt-oss then frontier teacher (the hard training data).
4. Re-export, dedup, and when pairs.jsonl ≥ ~2-5k → SFT→GRPO the specialist.
