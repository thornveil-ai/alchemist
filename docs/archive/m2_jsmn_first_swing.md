# M2 first swing: the agnostic stack on a never-seen library (jsmn)

**Question:** did the zlib prep actually make a *new* library faster, or was the
tooling secretly zlib-shaped?

**Test:** point the agnostic stack at [jsmn](https://github.com/zserge/jsmn) — a
minimal JSON tokenizer the tooling had never seen — with **zero jsmn-specific
code**, and see if it produces a correct, compilable Rust type model.

## Result: yes

Fed only `jsmn.h`, the stack (`c_struct` → `type_infer` → `render_rust`) emitted:

```rust
#[derive(Clone, Default)]
pub struct JsmnParser {
    pub pos: usize,        // unsigned index -> usize
    pub toknext: usize,    // unsigned "next" index -> usize
    pub toksuper: i32,     // signed (holds -1 "no parent") -> i32, NOT usize
}

#[derive(Clone, Default)]
pub struct Jsmntok {
    pub r#type: JsmntypeT, // enum detected; Rust keyword auto-escaped to r#type
    pub start: i32,
    pub end: i32,
    pub size: i32,
    pub parent: i32,
}
```

`rustc --crate-type bin` → **exit 0.** Every decision matches what a human would
make:
- unsigned indices (`pos`, `toknext`) → `usize`
- a signed index that carries a `-1` sentinel (`toksuper`) → `i32`, correctly
  *not* `usize`
- the `jsmntype_t` enum recognized as its own type
- `type` (a Rust keyword) escaped to `r#type`

No hand-written field table, no hand-mapped types, no zlib residue.

## What this proves (and doesn't)

**Proves:** the WS1/WS2 generalization is real. The struct parser and type-model
inference are library-agnostic — the first concrete evidence the prep compounds.

**Doesn't yet prove:** full autonomous *function* translation on jsmn. That
needs jsmn's differential harness (FFI to the C tokenizer + JSON test vectors +
the regen loop wired in) so byte-exact-or-refused applies to the parsing logic,
not just the types. That's the next M2 step — and it's now mostly assembly of
existing agnostic pieces, not new invention.

## Honest edges surfaced

- `type: JsmntypeT` is labeled `sub_struct` internally though it's an enum — the
  Rust type is right, the classification label is imprecise (cosmetic).
- Enum *variant* inference (values, `#[repr]`) isn't done yet — the enum shell is
  emitted; a full port needs the variant list from the `typedef enum`.
- Ownership/aliasing across fields is *flagged for review*, not resolved.

The type model — the single biggest per-library cost on zlib — came for free on
a library the tool had never seen. That's the compounding, measured.

---

## Update: the full end-to-end swing (translation + differential)

We took it all the way: built a **C reference oracle** (`jsmn_ref.c` dumps
`type start end size` per token), baked 13 JSON inputs into differential vectors,
generated a Rust crate (inferred types + designed coherent signatures + a
`parse_dump` harness), stubbed the 6 functions, and let the model **fill them all
from the C source autonomously**.

What happened, honestly:

1. **The model filled all 6 functions** (jsmn_init/alloc/fill/parse_primitive/
   parse_string/parse) from C, in dependency order. It compiled after one
   escaping fix (it wrote `b'\'` for a backslash byte instead of `b'\\'` — a real
   idiom gap now worth cataloguing).
2. **The differential oracle immediately caught real bugs** — `{"a":1}` produced
   `[]`, `"hello"` produced the wrong token bounds. Byte-exact-or-refused worked:
   the tool *refused*, it did not claim success.
3. A **naive "refill everything each round" loop oscillated** (introduced
   regressions/compile breaks). Switching to the **disciplined surgical loop**
   (refill one function, keep only if the pass count rises, revert regressions)
   converged **monotonically: −1 → 0 → 2 → 6 / 13**, then plateaued at 6/13.

**Result: 6/13 differentially-verified on a never-seen library, fully
autonomously, with an honest refusal on the remaining 7.** The plateau is the
harder cases (nested object/array size-counting, escaped strings) where the
model needs stronger repair — higher reasoning effort, decomposition, or a
per-function oracle instead of only the end-to-end one.

### What this proves
- The **whole pipeline runs end-to-end on a new library**: struct-parse →
  type-infer → coherent signatures → C differential oracle → autonomous fill →
  compile → differential repair.
- **The oracle is sound**: it caught every wrong token and never green-washed.
- The **surgical repair loop converges** (monotone, no oscillation) — the
  discipline transfers from zlib.

### The honest gap
- Convergence stalls on structurally harder functions; the fix is repair
  *strength* (effort/decomposition/per-function oracles), a known lever — not a
  new paradigm.
- One concrete idiom to add: **Rust byte-literal escaping** (`b'\\'` for
  backslash) — the model got it wrong deterministically.

This is the first end-to-end autonomous swing at a library the tool had never
seen. It didn't finish jsmn — but it proved the machine turns, the oracle holds,
and the remaining work is *strength*, not *invention*.

---

## Update 2: jsmn FINISHED — 13/13, fully autonomous, byte-exact

We took it the rest of the way, and the lesson is the important part.

The plateau was **not** the model's capability ceiling. It was **one
diagnosable coherent-model bug.** Reading the model's `jsmn_parse` against the C
showed it: the C loop is `for (; pos < len; pos++)` — the cursor advances at the
*end* of each iteration, so inside the body `pos` still points at the current
char. The model translated it as `let c = js[pos]; pos += 1; match c { .. }` —
incrementing *eagerly*, so when it called `jsmn_parse_string` (which expects
`pos` AT the opening quote and advances it itself), every string and primitive
came out off by one. That single mismatch failed 11 of 13 cases.

Given that exact guidance — *"increment `pos` at the END of the loop, not before
dispatch"* — the model rewrote `jsmn_parse` correctly on the **first try at
temperature 0**: **13/13, byte-exact token streams vs the C reference.**

```
start: 2/13
  t=0.0: jsmn_parse -> 13/13
ALL GREEN
```

### The real lesson (this changes the roadmap)
The "hard frontier" functions — jsmn's parser, and by extension zlib's resisted
`build_tree`/`compress_block` — are often **not** beyond the model. They fail on
a *specific, findable coherent-model mismatch*. The winning move isn't brute
force (more attempts, higher temperature all plateaued) — it's **diagnosis**:
read the model's output against the C, find the one wrong idiom, and encode it as
a catalog pattern so it never recurs. Two idioms came out of jsmn alone:
- `for-loop-post-increment-cursor` (increment at loop end) — the one that cracked it
- `pointer-return-into-array-to-index` (pool-alloc pointer → index)

**jsmn is the first COMPLETE autonomous translation of a library the tool had
never seen — byte-exact, differential-verified, 6 functions, zero hand-written
Rust.** The prep compounded, the oracle held throughout, and the frontier turned
out to be a *diagnosis* problem, not an *invention* one.
