# Path to autonomy: any C library, fully automatic

> Sequel to [PATH_TO_FLAWLESS.md](PATH_TO_FLAWLESS.md). That doc was about making the *output* flawless. This one is about removing the *human* — going from "a person + Alchemist translated zlib byte-exact" to "`alchemist translate <c-lib>` produces verified safe Rust with no human in the loop, on libraries it has never seen."

## The honest starting line

We proved the thesis on zlib ([case study](zlib_case_study.md)): differential oracles carry a real, hard C library — state machine, `goto`, unions, pointer aliasing, bit-twiddling — to byte-exact safe Rust. But it took a human (the assistant) doing specific things the pipeline could not:

| What a human did on zlib | Why it's the mountain |
|---|---|
| Designed the differential oracles (shim runners, stream/window snapshots) | The oracle is the correctness engine — it must build itself |
| Decided the coherent type model (drained-`Vec` input, `codes` offsets, ownership) | Pointer C → owned Rust is a modeling problem, not a syntax one |
| Hand-wrote the `inflate()` control-flow skeleton (`goto`→labeled break) | `goto`/state-machines need CFG-aware structuring the LLM can't wing |
| Diagnosed & repaired the ~9 integration bugs the oracle flagged | The oracle *finds* wrongness; something must *localize and fix* it |
| Provided a compilable C reference + toolchain | Fully-auto needs to build the library + harness itself |
| Recognized C idioms (advancing pointer, union, aliasing, sentinels) | These recur across libraries — they should be a learned catalog |

**Every row above is a workstream.** The plan is to automate each, keep the one invariant that makes this worth doing — *byte-exact-or-refused, never a fake green* — and prove it on a ladder of progressively harder libraries.

## The non-negotiable invariant

Everything below is subordinate to this: **no claim of success without a differential-oracle proof against the real C.** Autonomy must never be bought by lowering the bar. A fully-automatic run that can't prove byte-exactness must *refuse and report*, not guess. This is the moat; protect it.

---

## Workstreams

Each is a capability a human supplied on zlib. "DoD" = definition of done.

### WS1 — Automated oracle synthesis
Turn a C function + the compiled library into a differential harness with no human.
- Signature → FFI/shim binding generation (we hand-wrote every `shim_run_*`).
- **Effect-footprint inference**: what state does the fn read/write? The oracle must compare exactly those. (On zlib we knew `_tr_tally` touches `sym_buf`/freqs/`matches`; that must be derived.)
- Per-type input fuzzing (bytes, structs, valid-Huffman-code generators like we built by hand).
- State-mutator shim generation for stateful fns (the deflate/inflate state shims).
- **DoD**: given `(header, compiled .so, fn)`, emit a harness that fuzzes and captures return + full effect footprint, zero human edits.

### WS2 — Coherent-model & ownership inference
Automate the C-pointer-graph → owned-Rust-types decision we made by hand.
- **Aliasing detection**: which C pointers alias the same memory? (`s->dyn_ltree` ≡ `l_desc.dyn_tree`.) Drives the `mem::take` bridge or shared-ownership choice.
- **Buffer model**: `ptr+len` → slice/`Vec`; advancing pointer → drained `Vec` or offset (the `next_in`/`codes` decisions).
- **Ownership graph**: who owns whom (`DeflateStream` owns `DeflateState`; stream-using fns take `&mut DeflateStream`).
- Union → enum or split fields (`ct_data.fc`/`.dl`).
- **DoD**: a coherent type + signature model inferred from the struct graph + usage, that compiles and round-trips through the oracle.

### WS3 — Control-flow translation (the hard one)
Structured Rust from `goto`-heavy / state-machine C. This is a compiler problem, not a prompt.
- Build the CFG; detect irreducible flow; apply relooper-style structuring (labeled loops/breaks, or state-enum + `loop`/`match` — which is what `inflate()` became).
- Macro-based control flow (`NEEDBITS`→`goto`) → inlined idioms.
- **DoD**: `goto`-based C functions translate to structured safe Rust automatically and pass the oracle. `inflate()` is the acceptance test — re-derive it with no hand-written skeleton.

### WS4 — Autonomous diagnose-and-repair
Close the loop the human closed 9 times: oracle diff → localize → fix → verify.
- Differential diff → suspect localization (bisect the call graph; find the first byte/field that diverges and the fn responsible — how we found `scan_tree`'s `max_count` from a 15-byte block).
- Repair generation: re-inject the fn with the *exact* discrepancy as guidance (the "inject-C + iterate on the oracle's discrepancy" method, but agent-driven).
- Verify-or-revert; bounded retry; escalate/refuse on non-convergence.
- **DoD**: the 9 zlib bugs (or equivalents) get caught *and fixed* with no human diagnosis.

### WS5 — Harness & environment generation
Build the library + harness itself.
- Build-system detection (make/cmake/autotools), dependency resolution, sandboxed compile.
- Non-determinism handling: seed control, mock/trap time/random/IO so the reference is deterministic (or the oracle refuses).
- **DoD**: `alchemist translate <git-url>` compiles the C reference + harness unattended.

### WS6 — C-idiom pattern catalog (the learning layer)
A growing library of `C-idiom → Rust-model` transforms, applied by the pipeline and injected into the model's context.
- Seed it from zlib: advancing pointer→drained `Vec`, union→fields, alias→`mem::take`, `0xffff` sentinels, wrapping arithmetic, macro expansion, the `+1` lookahead sentinel.
- Each new library contributes patterns; regressions guard them.
- **DoD**: a versioned catalog + a mechanism that matches idioms in new C and pre-supplies the model with the right pattern.

### WS7 — Scale & orchestration
zlib is a few-thousand lines driven function-by-function. Real libraries are bigger.
- Call-graph topological ordering (leaves first — exactly how we went checksum→trees→deflate→inflate).
- Parallel per-function fan-out (the `Workflow` primitive already exists).
- Incremental oracle verification as each fn/module lands.
- Reuse the **durability backbone we already built** (`restore_hardports`: hydrate a fresh skeleton from git-tracked verified bodies — proven this session by restoring 320 tests from git alone). Scale it to thousands of functions.
- **DoD**: a 100K+-line library translated with bounded context and parallel verification.

---

## The milestone ladder

Progressively harder targets, each forcing more of the workstreams. **De-risked by design**: M1 re-does a target we *know* is achievable, so any failure is a tooling gap, not an unknown.

| # | Target | Proves | Autonomy bar |
|---|---|---|---|
| **M0** ✅ | zlib | The thesis | Semi-automatic (done) |
| **M1** | zlib, from a clean checkout | WS1–4, WS6 on a known-good target | **Zero** human oracle/modeling/repair |
| **M2** | 3–5 small/medium libs (jsmn, a hash lib, a small codec) | Generality of WS1–4/6 | Zero |
| **M3** | libpng (depends on zlib) or similar | WS5 + dependency handling | Zero |
| **M4** | a 100K+-line library | WS7 scale | Zero |
| **M5** | an N-library benchmark suite | "any" — report the honest pass rate + failure taxonomy | Zero |

The **[M1 autonomy scorecard](autonomy_scorecard_baseline.md)** makes this concrete. It inventories the human-supplied artifacts the pipeline still needs to translate zlib and classifies each by workstream. Baseline today:

| Workstream | Open debt | What it is |
|---|---:|---|
| WS3/WS4 | 382 | Human-ported Rust function bodies (the core debt) |
| WS1 | 123 | Hand-written oracle shim runners |
| WS3 | 10 | Curated reference implementations |
| WS2 | 8 | Hand-specified type-model overrides |
| **Total open** | **523** | (+ 14 idioms already retired by WS6) |

Re-run `python -m alchemist.autonomy.scorecard` after every change. **M1 = drive open debt to zero** while keeping every gate byte-exact-or-refused.

**M1 is the forcing function.** Re-deriving zlib fully automatically converts every manual move from this session into a measured capability, against ground truth we already have. Start there.

## Definition of "conquered"

Not a vibe — a number. A public benchmark of **N diverse real C libraries**, where `alchemist translate <lib>` runs unattended and, for each, either:
- produces safe Rust that passes a **byte-exact differential** across its public API, **or**
- **refuses** with a precise, honest reason (unbuildable oracle, irreducible control flow, non-determinism).

Report the pass rate and the **failure taxonomy** openly. "Any library" is honest when the taxonomy is small and the pass rate is high on the classes we claim.

## Risks & open questions (name them, don't bury them)

- **Irreducible control flow** — some `goto` patterns don't structure cleanly; may need a state-machine fallback with a perf/readability cost.
- **No deterministic reference** — IO, threads, wall-clock, `rand`, UB. The oracle must detect and *refuse*, not silently encode nondeterminism (or the C's UB).
- **Model inference non-convergence** — deeply pointer-entangled code (intrusive linked lists, arenas) may resist clean ownership inference.
- **Cost at scale** — large libraries = large compute; WS7 must keep it bounded (incremental verify, cache/hardport reuse).
- **UB in the reference** — if the C relies on UB, "byte-exact vs C" can mean "matches a specific compiler's UB." Flag divergence across `-O` levels / compilers as a signal.

## Onboarding the next library

The repeatable process — what is reusable vs per-library, and the exact sequence — is in **[ONBOARDING_A_LIBRARY.md](ONBOARDING_A_LIBRARY.md)**. WS1 shim synthesis and the WS4 regen loop are now library-agnostic; the main per-library cost is the WS2 coherent type model.

## Where to point first

1. **WS1 + WS4 on M1** — automated oracle synthesis and the autonomous repair loop, targeting a push-button zlib. These two convert the most human effort into capability and are directly measurable against known-good output.
2. **Seed WS6** from the zlib idiom set (cheap, high leverage, compounds on every later library).
3. **WS3** (`inflate()` re-derivation) is the deepest technical risk — prototype it early even if M1 uses a fallback, so the timeline knows the shape of the hard part.

The mountain is real, but it's *charted*: every step is something a human already did once, on a target that already works. Automate those, keep byte-exact-or-refused sacred, and climb the ladder.
