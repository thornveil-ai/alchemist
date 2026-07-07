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

## AFTER Phase 1 fixes (2026-07-07, same suite, same conditions)

| function | class | triage | implement | verify | overall |
|---|---|---|---|---|---|
| `isqrt` | math-scalar | ATTEMPT | PASS | FAIL | **FAIL** (model fill overflows u32 — verifier caught it) |
| `popcount` | bits-scalar | ATTEMPT | PASS | FAIL | **FAIL** (unsigned-long FFI width edge) |
| `fletcher16` | checksum-buffer | ATTEMPT | PASS | PASS | **PASS** ✅ first cold autonomous translation |
| `str_reverse` | string-inplace | ATTEMPT | PASS | FAIL | **FAIL** (in-place shape) |
| `parse_int` | parser-buffer | ATTEMPT | PASS | FAIL | **FAIL** (char*→&str lift) |
| `xorshift` | stateful-prng | ATTEMPT | PASS | FAIL | **FAIL** (state) |
| `rc4` | stateful-cipher | ATTEMPT | (implement FAIL) | - | **FAIL** (struct not carried) |
| `bump_alloc` | stateful-allocator | SKIP | - | - | **FAIL** (still triaged glue) |

- **Triaged in: 12% → 88%** · **Passed implement: 12% → 75%** · **Passed verify: 0% → 12%** · **OVERALL: 0% → 12%**
- The pipeline went from *translating nothing unseen* to **filling arbitrary cold code (6/8 compile + pass TDD)**, with the differential correctly gating correctness: only `fletcher16` is byte-exact; the other fills are subtly wrong and the verifier catches them (no fake greens).
- **The remaining verify gap is fill quality / repair-loop convergence**, not plumbing — every function now reaches a real differential.

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
