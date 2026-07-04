# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
