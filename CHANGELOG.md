# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **A real external cryptographic library, translated end-to-end.**
  `alchemist translate subjects/siphash` — the genuine veorq/SipHash-2-4
  reference (CC0, not authored here) — reaches **OVERALL: PASS** with
  Gemma 4 31B Dense in the loop: byte-exact against the compiled reference
  (canonical vector and thousands of fuzzed messages), zero hand-edits.
  Receipt: `docs/receipts/siphash-2026-07-04.json`. Getting there taught
  the pipeline to handle a keyed byte-digest hash with an out-param
  (a whole hash family: SipHash/SHA/HMAC/BLAKE) and — the decisive fix —
  to feed the model the C `#define` macros a function references
  (`SIPROUND`, `ROTL`), which is why the model finally produced the exact
  ARX rounds instead of guessing them. It also surfaced eleven general
  pipeline fixes (below), none SipHash-specific.
- **Generalization proven on a second, independent subject.**
  `alchemist translate subjects/hashkit` — FNV-1a (u32), CRC-16/CCITT-FALSE
  (u16) and the BSD rotate-add sum (u16), algorithms and widths distinct from
  tinychk — runs end-to-end with Gemma 4 31B Dense and prints **OVERALL:
  PASS**, all three functions model-written on the first iteration and
  byte-exact against a compiled hashkit oracle. Getting there fixed three
  general pipeline bugs (below), none tinychk- or hashkit-specific. Receipt:
  `docs/receipts/hashkit-2026-07-04.json`.
- **First complete automated C→Rust translation (ROADMAP M09).**
  `alchemist translate subjects/tinychk` runs all six stages with the local
  model (Gemma 4 31B Dense) in the loop and prints **OVERALL: PASS** — zero
  hand-edits to generated code. adler32, crc32, and fletcher16 are
  model-written and byte-exact against a freshly compiled tinychk oracle
  across 5000 random inputs each (21 differential tests, receipt sealed);
  crc32's lazy static table became a locally-computed table and its
  initializer a no-op. This is the first birth-to-receipt run in the
  project's history, and it is subject-generic — no tinychk-specific code.
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
- Architecture module placement: the LLM architect sometimes listed function
  names (or scattered one source module's functions) in crate `modules`
  lists, so the module matched no crate and the skeleton emitted empty
  crates — nothing to fill, nothing to differentially adapt.
  `_reconcile_module_placement` now guarantees every spec module is claimed
  by exactly one crate and drops crates left empty.
- Standards-catalog false oracle: a boundary-blind prefix match handed
  CRC-32 (32-bit) vectors to `crc16_ccitt` (a 16-bit function), failing a
  correct implementation every iteration. Catalog matching now respects word
  boundaries — `crc32_z`/`adler32_impl` still resolve, `crc16_ccitt` matches
  nothing.
- Scalar-hash fuzzing: hash-category functions were always routed to the
  byte-digest fuzzer, which rejected FNV-1a's scalar u32 and left it
  unverifiable. A scalar-integer return is now fuzzed as a checksum.
- FFI oracle library naming and loader path: the differential oracle was
  built with a hardcoded Windows `.dll` name and no runtime library path, so
  on Linux the diff crate failed to link (`-lc_*_ref` not found) and, once
  linked, failed to load the `.so`. Names are now platform-correct
  (`.dll`/`.so`/`.dylib`) with a build.rs rpath and the oracle directory
  prepended to the loader-path variable for the test subprocess.
- The lazy-static-table idiom (a C function that fills a file-scope static on
  first use) now translates: the initializer becomes a no-op and consumers
  compute their own table, driven by a fill prompt that lists the
  module-level constants actually in scope.
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
