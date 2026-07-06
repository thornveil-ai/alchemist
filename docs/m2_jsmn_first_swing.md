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
