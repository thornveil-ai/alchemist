# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **First all-gates-green crate.** `alchemist verify subjects/zlib -p
  zlib-checksum` prints `OVERALL: PASS` — compile, anti-stub, no-unsafe,
  semantic, test (177/0) and differential (19/19) all green through the
  automated pipeline. The six remaining table-generation skeletons
  (`make_crc_table`, `get_crc_table`, `braid`, `write_table`,
  `write_table64`, and the MAKEFIXED/inffixed generator with a full
  `inflate_table` port) are now verified ports anchored byte-for-byte
  against zlib's shipped `crc32.h` and `inffixed.h`; hardports stored in
  `alchemist/references/impls/zlib_hardports/`.
- Checksum shim oracle (`zlib_checksum_shim.dll`): zlib's `local` statics
  (`crc_word`, `crc_word_big`, `multmodp`, `x2nmodp`) now have a compiled-C
  FFI oracle with W=8/N=5 compile-time pins. `crosscheck_checksum_shim`
  enforces shim-vs-pure-reference agreement before any vector is minted —
  an oracle disagreement halts generation. Independently confirms the
  crc_word_big W=8 fix against real compiled zlib
  (`crc_word_big(1) == 0x9630077700000000`).
- Verification receipts (`verifier/receipt.py`): every differential run
  writes `verify_gen/receipt.json` — gate results, harness bindings, case
  counts, boundary lengths, and the oracle's identity (gcc version, C
  source and DLL sha256) — content-addressed with an integrity hash and an
  optional HMAC (`ALCHEMIST_RECEIPT_KEY`).
- Compression adapters with full effect footprint: `rust_compress`/
  `c_compress` wrappers return `(status, bytes)` — no asserts inside
  wrappers — and the harness checks status parity, both roundtrips, and
  cross-interop. The zlib deflate harness now resolves (3/3 adapted) and
  fails honestly on the stub implementations instead of being unresolvable.
- Boundary-length differential tests: deterministic LCG-content tests at
  algorithmic fold edges (Adler NMAX 5551/5552/5553, CRC word/braid/batch
  alignments) that random sampling almost never hits.
- Oracle-tagged vector persistence: fuzz vectors are stamped with their
  oracle's content hash (`[oracle:shim:zlib_checksum_shim.dll:<sha16>]`)
  and persisted into the spec checkpoints. Tagged vectors always regenerate
  on the next run — a persisted vector can never outlive a fix to its
  oracle — while authored vectors are never touched.
- Automated differential adapter (`verifier/adapter_gen.py`): the Stage-5 gate
  now discovers the generated crates' real `pub fn` signatures, emits
  `c_*`/`rust_*` wrapper code and path-deps automatically, and turns any
  harness it cannot adapt into a failing test. First genuine automated
  differential green: zlib-checksum, adler32 + crc32, 5000 random cases each
  vs the compiled C reference, zero hand-editing.
- Semantic-lint verify gate: `semantic_lints.scan_workspace_semantics` sweeps
  every generated function against its spec at verify time;
  `VerificationReport` gains a `semantic` gate that fails closed on
  errors. New `lint_crc32_braid` catches the big-endian word-braid variant
  confusion (the #1 named failure mode) — proven with negative tests.
- `--package` scoping for `alchemist verify` and `DifferentialConfig.packages`
  so a completed crate can be verified while sibling crates are still
  skeletons.
- `zlib_checksum_diff_config()` — checksum-crate-scoped differential config.
- `docs/PATH_TO_FLAWLESS.md` — the assurance roadmap: per-function
  verification levels (L0–L6), the oracle-integrity/fuzzing/proof gap
  program, and the "flawless-or-refused" end-state with signed receipts.
- Initial CHANGELOG.md — establishes Keep-a-Changelog format

### Fixed
- crc_word_big translation and its pure-Python fuzz reference implemented a
  chimera of zlib's W=4 and W=8 braid configurations (32-bit-swapped table
  entries in the low half driving a 64-bit loop). Both now implement the real
  W=8 variant — `crc_big_table[i] = byte_swap64(crc_table[i])`, entries in
  the high 32 bits, anchored against zlib's shipped crc32.h. The 17
  previously-failing `test_crc_word_big` vectors now pass (183/183 in
  zlib-checksum).
- Differential harness generation no longer falls through to a smoke-only
  check for unhandled algorithm categories: `transform`/`protocol`/
  `scheduler`/`other` now emit an UNVERIFIABLE harness that fails, so the
  weakest check is never the default.
- Test emitter renders expected values against the function's actual Rust
  return type: `Option`/`Result` constructors pass through (`Some(18usize)`
  no longer mangled into `b"Some(18usize)"`), byte-string fallback only for
  byte-like returns, and unrenderable values emit a failing test instead of
  uncompilable code. The zlib-compression test module compiles and runs
  again (and honestly fails on the stub implementations).
- `alchemist verify` CLI updated to the current `DifferentialTester` API (was
  calling a long-removed constructor shape and dict-style report).
- Removed the orphaned `zlib_config.WRAPPERS_RS` dead code, replaced by
  adapter_gen.
- FFI import libraries are now named `lib<name>.dll.a` (MinGW convention,
  matches the proven hand-written layout).

[Unreleased]: https://github.com/thornveil-ai/alchemist/compare/HEAD...main
