# base64 — first-shot autonomous translation (M2)

WEI Zhicheng's public-domain base64 (github.com/zhicheng/base64), translated
C→safe Rust fully autonomously in ONE fill: **32/32 differential tests
(16 encode + 16 round-trip) byte-exact vs the C reference, zero repair.**

- `lib.rs` — the verified Rust (coherent skeleton: tables/consts as data; the two
  functions filled by the model from base64.c).
- `setup_base64.py` — reproducible harness: builds the C oracle, generates the
  differential vectors, emits this crate skeleton.

See `docs/m2_base64_clean_translation.md` for the write-up (the compounding,
measured: zlib=heavy → jsmn=1 diagnosis → base64=first-shot).
