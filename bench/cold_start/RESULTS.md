# Alchemist Cold-Start Baseline (Phase 0)

**Run:** 2026-07-07, Gemma 4 31B on the RigRun box, shipping `alchemist` pipeline.
Each function is a **never-seen** self-contained C function, run through the pipeline
**COLD** — no per-subject config, no oracle hand-off, **zero human touches**.
`triage` = did the classifier *attempt* it (vs skip it as "glue" and do nothing).

| function | class | triage | analyze | extract | architect | implement | verify | overall | s | calls |
|---|---|---|---|---|---|---|---|---|---|---|
| `isqrt` | math-scalar | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 39.6 | 0 |
| `popcount` | bits-scalar | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 41.0 | 0 |
| `fletcher16` | checksum-buffer | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 31.0 | 0 |
| `str_reverse` | string-inplace | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 48.2 | 0 |
| `parse_int` | parser-buffer | ATTEMPT | PASS | PASS | PASS | PASS | FAIL | **FAIL** | 57.8 | 1 |
| `xorshift` | stateful-prng | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 54.6 | 0 |
| `rc4` | stateful-cipher | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 45.3 | 0 |
| `bump_alloc` | stateful-allocator | SKIP | PASS | PASS | FAIL | - | - | **FAIL** | 57.2 | 0 |

## Honest numbers (n=8)
- **Triaged in (even attempted, not skipped as glue): 12%** (1/8)
- **Passed implement (compiled + tests): 12%** (1/8)
- **Passed verify (differential): 0%**
- **OVERALL PASS cold, zero human touches: 0%** (0/8)

## How to read this (scoring caveats)
- `analyze`/`extract` show **PASS** even for SKIP rows — that is a *trivial* pass: the file
  parsed and there were **0 algorithm modules to extract**. The real signal for skipped
  functions is **triage=SKIP + 0 LLM calls = nothing was translated.** `architect` then
  shows FAIL because it ran with 0 modules.
- Only **`parse_int`** was actually attempted (1 LLM call). It reached `verify` — i.e. it
  triaged in, recovered a spec, designed a crate, produced compiling Rust — and then
  **failed the differential** (wrong output vs the C reference). So even the one success
  path ends in a correctness miss, not a green.

## AFTER Phase 1 — COMPLETE (2026-07-07)

The pipeline autonomously translates and **byte-exact-verifies clean single C functions across
every common signature shape**, COLD (zero human touches). Functions whose C reference has
undefined behaviour are correctly **REFUSED** — byte-exact-or-refused, no fake greens.

| function | class | shape | triage | implement | verify | overall |
|---|---|---|---|---|---|---|
| `fletcher16` | checksum-buffer | checksum | ATTEMPT | PASS | PASS | **PASS** ✅ |
| `popcount` | bits-scalar | scalar | ATTEMPT | PASS | PASS | **PASS** ✅ |
| `str_reverse` | string-inplace | in-place | ATTEMPT | PASS | PASS | **PASS** ✅ |
| `bitsqrt` | math-scalar (clean) | scalar | ATTEMPT | PASS | PASS | **PASS** ✅ |
| `atoib` | parser-buffer (clean) | buffer→scalar | ATTEMPT | PASS | PASS | **PASS** ✅ |
| `isqrt` | math-scalar | scalar | ATTEMPT | — | REFUSE | **REFUSE** — C has divide-by-zero UB at `UINT_MAX` |
| `parse_int` | parser-buffer | buffer→scalar | ATTEMPT | — | REFUSE | **REFUSE** — C has integer-overflow UB |
| `xorshift` | stateful-prng | scalar-state mutator | ATTEMPT | PASS | PASS | **PASS** ✅ first stateful cold-green (Phase 2) |
| `rc4` | stateful-cipher | array-struct + sequence | ATTEMPT | PASS | PASS | **PASS** ✅ flagship stateful cipher (Phase 2) |
| `bump_alloc` | stateful-allocator | pointer-struct + alloc-seq | ATTEMPT | PASS | PASS | **PASS** ✅ pointer-field allocator (Phase 2) |
| `fnv` | stateful-hash (3-fn lib) | hash-sequence | ATTEMPT | PASS | PASS | **PASS** ✅ first >2-fn library (Phase 2) |
| `rollcksum` | checksum + static helper | checksum | ATTEMPT | PASS | PASS | **PASS** ✅ static helper inlined (Phase 2) |
| `wsum` | 2-fn lib, inter-calling | checksum×2 | ATTEMPT | PASS | PASS | **PASS** ✅ 2 public fns, both verified (Phase 2) |
| `mathlib` | multi-dir library | checksum + WALL-4 | ATTEMPT | PASS | PASS | **PASS** ✅ subdir src + header + excluded test/main (Phase 2) |
| `gentest` | Makefile-generated source | scalar + auto-build | ATTEMPT | PASS | PASS | **PASS** ✅ pipeline runs make to generate a needed header (Phase 2) |
| **libcrc crc32** (REAL, never-seen) | multi-scalar + checksum | crc_32 + update_crc_32 | ATTEMPT | PASS | PASS | **PASS** ✅ real 3rd-party library module, byte-exact (Phase 2 acceptance) |
| **libcrc crc8** (REAL, SHT75 variant) | inline-table checksum + multi-scalar | crc_8 + update_crc_8 | ATTEMPT | PASS | PASS | **PASS** ✅ non-standard CRC variant, byte-exact (Phase 2) |
| **libcrc crc16** (REAL, runtime table) | runtime-table checksum (3 fns) | crc_16 + update + init | ATTEMPT | PASS | PASS | **PASS** ✅ runtime-computed table translated (Phase 2) |

### Phase 2 acceptance (2026-07-08): real never-seen library
`libcrc` (Lammert Bies, MIT) fetched fresh from GitHub and run **blind**. The **crc32 module**
(`crc_32` + `update_crc_32`) translates to safe Rust and verifies byte-exact vs the compiled C —
a genuinely never-seen third-party library, not a crafted benchmark. Two capabilities made this
autonomous: the **multi-scalar shape** (`update_crc_32(uint32_t, unsigned char) -> uint32_t`) and
**auto native build** (`prepare_native_build` runs the library's own `make` to materialize the
build-time-generated CRC lookup table, so no manual build is needed — proven end-to-end on `gentest`).
**Honest frontier:** pointing at the WHOLE 11-module libcrc repo in one shot fails at the *architect*
stage (it can't design 11 interdependent modules at once). Solved with **per-module orchestration**
(`translate-lib`, concurrent) + a batch of fill-quality fixes.

### Phase 2 EXIT (2026-07-08): never-seen library → ONE unified verified workspace, 0 human touches
The TRACTOR-parity milestone. `alchemist translate-lib /path/to/libcrc` — **one command, zero human
touches** — fetches nothing hand-written: it runs the library's own build, discovers the 9 real
`src/*.c` modules (build-tool dirs like `precalc/` excluded), translates each module concurrently,
then **assembles the modules that verified byte-exact into a single cargo workspace** with a shared
type model and proves the whole tree builds + tests **together**:

```
Library result: 9/9 modules verified   (crc16 crc32 crc64 crc8 crcccitt crcdnp crckrmit crcsick nmea — each byte-exact vs its compiled C)
Assembling verified modules into one unified workspace…
  members: crc16-algos, crc16-core, crc32-core, crc64-algo, crc64-core, crc8-core,
           crcccitt, crcccitt-core, crcdnp-core, crcdnp-traits, crckrmit-core,
           crckrmit-traits, crcsick-core, nmea-checksum   (14 crates)
  cargo build --workspace: PASS   cargo test --workspace: PASS
```

`workspace_receipt.json`: `{modules_verified: 9/9, cargo_build_workspace: true, cargo_test_workspace:
true, human_touches: 0}`, **0 `unsafe`** across the whole workspace. This is the Phase-2 deliverable
at 100%: a real never-seen stateful library → **one** verified Rust workspace of 14 crates,
autonomously, every module byte-exact vs its own compiled C. The climb from the first cold run
(4/9, partial) to 9/9 drove a batch of general fixes, each of which makes the pipeline better on ANY
library: **compiled-C byte-exact differential is authoritative over any heuristic lint** (ended the
`lint_crc32` false-refusal → crc32); **callee-context fed to the fill** so a standalone updater sees
the shared table's init and reproduces it (crc16/crcdnp); **static helpers inlined into callers**
(crc_ccitt_generic → crcccitt; init tables → crckrmit); a **C-string-in → buffer-out shape** (nmea);
module-name identifier sanitization (`nmea-chk`→`nmea_chk`); dropping the architect's trait/error
**over-design for infallible modules**; and normalizing the model's filled fn name to the skeleton's
(`checksum_NMEA`→`checksum_nmea`). New assembly machinery: `workspace_assembler` (identical shared
items hoisted to a `<lib>-types` crate; name-conflicting defs left module-local, never merged;
multi-crate module outputs carried whole).

**libcrc per-module scorecard (2026-07-08), driven via `translate-lib`:**
| module | shape | result |
|---|---|---|
| crc32 | precomputed-table checksum + multi-scalar | **PASS** (2/2) |
| crc8 | inline-table (SHT75 variant) | **PASS** (2/2) |
| crc16 | runtime-computed table (3 fns) | **PASS** (3/3) |
| crckrmit | runtime-computed table | **PASS** (2/2) |
| crc64 | inline 256×u64 table gen ×3 fns | crc_64_we was lint-blocked (fixed); slow to reverify |
| crcccitt | parameterized generic helper | 4/5 (crc_ccitt_generic diverges) |
| crcdnp | 16-bit runtime table | 0/2 (E0220 codegen error, fill quality) |
| crcsick | non-standard byte manip | 0/? |
| nmea-chk | output-BUFFER writer (`f(in, out)->ptr`) | needs a new output-buffer shape |

**From 1/11 (pre-fixes) to 4 confirmed green + 1 near (crc64) + 1 partial (crcccitt 4/5)** on a real
never-seen library — every green byte-exact vs the module's own compiled C. Fixes that drove it:
recursive C-source feed, const-table carry, variant-KAT gate (main + differential), void-noarg
skip, multi-scalar shape, 32-bit CRC-lint gate. Remaining = a per-function long tail (a generic
helper, one codegen error, one new output-buffer shape) — NOT systemic.

### Phase 2 progress (2026-07-07)
- **First stateful function verified cold: `xorshift_next`** — a scalar-state mutator
  (`fn(&mut u64) -> u64`) differentially verified over 4000 fuzzed initial states vs the
  compiled C. New machinery: `struct_lift.py` (tracked C-struct parser + Rust/FFI field
  mapping) + a scalar-state **mutator differential shape** (classify → oracle drives C on
  fuzzed state+args, captures `(return, post-state)` → adapter tuple wrappers → proptest).
  The single-scalar struct is carried as a bare `&mut <int>`; the C struct pointer is bridged
  via a `c_typedefs` override, so no FFI struct is needed.
  *(Honest note: the trivial `xorshift_seed` one-line setter is dropped by the extractor as
  glue; the PRNG core `next` is what's verified.)*
- **`rc4` flagship stateful cipher — cold-green (2026-07-07).** RC4 (256-byte s-box + i/j,
  `init` + `keystream`) translates C→safe Rust and is byte-exact verified two ways: (1) 20
  per-function TDD tests — a **state-observer** (post-init s-box/i/j match compiled C) + an
  **init→keystream sequence** (keystream matches C); (2) a **whole-crate FFI differential**
  (`rust_rc4` vs `c_rc4`, 2000 fuzzed `(key, outlen)` cases). New machinery: FFI `#[repr(C)]`
  mirror-struct injection, the `cipher_seq` differential shape, a crate-layout fix (trait-
  referenced error types → trait crate; drop architect-invented wrapper/builder skeletons).
- **`bump_alloc` — cold-green (2026-07-07). ALL 3 stateful benchmark functions now pass.**
  The pointer-field allocator translates C→safe Rust and verifies byte-exact: the raw `buf`
  pointer field is DROPPED (observably irrelevant to the returned offsets), and `bump_alloc_n`
  is verified via the **alloc-sequence differential** — init(buffer of size `cap`) then a
  fuzzed op sequence, `Result`→`i64` mapped, 2000 cases rust-vs-C + 24 state-observer/sequence
  TDD tests. Six walls cleared: triage (glue needs call evidence), struct-carry (spec type
  name), pointer-field drop, alloc-seq shape, init-arity handling, fill-loop arity guard.
  *(Reliability caveat: the extract is non-deterministic on the `capacity` param count (2 vs 3
  inputs); this run had a consistent 3-input spec. Hardening the extract/spec consistency is a
  follow-up so it's green every run, not most runs.)*

### Phase 2 → whole-library (in progress)
- **All 3 single-function stateful shapes certified green** with the committed code (re-ran to
  completion: xorshift, rc4, bump_alloc all OVERALL PASS). A regression was caught + fixed in the
  process: the spec-name struct-carry emitted a recursive `struct u64` for xorshift's single-scalar
  state — now skipped (single-scalar structs carry as `&mut <primitive>`, not a struct).
- **First >2-function stateful library COLD-GREEN: `fnv` (FNV-1a init/update/final).** OVERALL PASS.
  Two things landed: (1) fixed the extractor **single-scalar state inconsistency**
  (`fnv_init(&mut FnvState)` vs `fnv_update(&mut u32)`) via `normalize_single_scalar_state`; (2) built
  the **hash-sequence shape** — classify `init(S*) + update(S*, byte*, int) + final(S*) -> scalar`
  over a single-scalar state, oracle drives `init; update(data); final()` on fuzzed data → per-fn
  vectors (init/update observers + composed digest) + a whole-crate differential
  (`fnv_final_matches_c_reference`, 2000 fuzzed byte-vectors, rust vs compiled C). Model translated
  faithfully: `fnv_update` = `for &b in data { *s ^= b as u32; *s = s.wrapping_mul(16777619); }`.
  The 3 functions fill in declaration order (init→update→final), so the composed digest verifies.
  **4 stateful subjects now green: 3 single-function shapes + 1 real 3-function library.**

### Phase 1 scorecard
- **Clean single-function stateless: 5/5 = 100% cold-green** across 5 signature shapes
  (checksum, scalar, in-place, sqrt, buffer-parse).
- **UB-bearing C: 2/2 correctly REFUSED** — the differential catching genuine C bugs
  (`isqrt` div-by-zero, `parse_int` overflow). This is the byte-exact-or-refused contract
  working, not a pipeline failure.
- **Stateful (struct-carry): 3 → Phase 2** (out of Phase 1's single-function scope by design).
- **Triaged in: 12% → 100%.** Every green is byte-exact vs the compiled-C oracle; nothing faked.

### The climb (Phase 0 → Phase 1)
- **Triage:** 12% attempted → **100% attempted** (attempt-by-default replaced skip-as-glue).
- **Verify:** 0% cold-green → **100% of clean stateless** cold-green.
- Machinery landed: attempt-by-default triage · auto-oracle (compiled-C reference + fuzz) ·
  headerless `.c` parsing · 5 signature shapes · `char*`→`&[u8]` lift · faithful C-source
  translation · wrapping arithmetic · explicit-len fill vectors. All under CI green.

## What this proves (feeds the battle plan)
1. **WALL 1 (triage) is catastrophic and empirical.** 7/8 functions — including trivially
   translatable ones like `isqrt`, `popcount`, `str_reverse` — are silently skipped as
   "glue" because their *names* don't match the hardcoded `ALGORITHM_PATTERNS` catalog.
   The pipeline defaults unknown code to *do nothing*. Fixing this (Phase 1) is the single
   highest-leverage unlock: it converts "≈12% attempted" toward "≈100% attempted".
2. **The implement/skeleton stage is the second wall.** `rc4` (forced past triage in an
   earlier probe) and every stateful function faceplant at skeleton codegen (struct type not
   carried, pointer→slice params malformed). `parse_int` got past it but missed the diff.
3. **Baseline to beat: 0% cold autonomous.** Every future pipeline change re-runs this suite
   (see README) — the number must go **up**, never down.
