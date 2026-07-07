# Tier 1 autonomy — the capability unlocks (build, scale, diagnosis)

The auto-onboarder translated single, easy-to-compile leaf files. Tier 1 removes
the three things that were still *human*, so the tool can face real code.

## #1 Build/compile discovery (`build_discovery.py`)
Figures out how to compile a C target with no hand-written recipe: iteratively
`-fsyntax-only`, read the first missing-header error, resolve by FINDING the
header in the tree (add include dir) or STUBBING it (out-of-tree dep). Reports
stubs as an honesty boundary. **Validated:** auto-compiles real ArduPilot
`crc.cpp`, auto-stubbing `AP_HAL/AP_HAL_Boards.h` — the exact hand-work removed.

## #2 Multi-file / whole-repo (`build_crate_from_sources`)
Onboards a whole directory: tables/functions/consts merged across every `.c`,
the call graph recomputed over the union (cross-file calls), one differential
oracle compiled from ALL sources via build discovery. Static functions excluded
(a separate-TU harness can't call them). **Validated:** a 2-file library
(ArduPilot crc.cpp + base64.c) → 22 functions, 9 tables merged, one oracle,
merged crate compiles.

## #3 Automated diagnosis (`diagnose.py`) — the intelligence unlock
The deepest hand-jam was *me*: when a fill plateaus, a human reads the Rust vs C,
names the coherent-model mismatch, fixes it, writes the idiom. Now the model does
it: given C + wrong Rust + the differential failure, produce
{root_cause, general_rule, fixed_function}, apply, test, iterate — refusing
success unless the test passes. **Validated:** handed a known-buggy `base64_decode`
(push/pop instead of an output index) with NO human idiom, it diagnosed in one
round — *"C uses a manually advanced output index; map to direct indexing, not
push/pop"* — and drove it to 24/24 byte-exact. The `general_rule` it emits is a
catalog-ready idiom, so the tool gets smarter every time it's stuck.

## What this means
The spine is now autonomous through the hard parts: **get real code to compile,
scale past one file, and self-diagnose when a function is hard.** What remains for
TRACTOR parity is *coverage* (stateful struct APIs, more signature shapes,
fuzz-depth verification) — more patterns of the same shape, not new capability.
