# M2, second library: base64 — first-shot clean translation (the compounding, measured)

**Question:** the idiom catalog grew a lot while cracking zlib's tail (debug-macros,
field-aliases, borrow-split, array-sizing, const-inline) — but every one of those
was *found on zlib*. Do they actually generalize, or is the catalog secretly
zlib-shaped? And does a new library go **faster** now than jsmn did?

**Test:** point the stack at [base64](https://github.com/zhicheng/base64) (WEI
Zhicheng, public domain) — a JSON-tokenizer-free, never-seen codec — with zero
base64-specific code, and measure how much repair it needs.

## Result: 32/32 on the FIRST fill, zero repair

The coherent skeleton (tables + `BASE64_PAD` provided as pure data; the two
functions stubbed) plus one autonomous fill from the C:

```
refill(base64_encode): body rewritten (997 chars)
refill(base64_decode): body rewritten (1021 chars)
=== after fill: 32/32 ===
```

16 encode vectors + 16 round-trip vectors (`decode(encode(x)) == x`), across
padding edges (0–6 byte inputs), random bytes, and known strings — all
byte-exact vs the C reference. **No surgical loop, no diagnosis, no temperature
sweep.** The model reproduced the C's exact state-machine encode (the `s` phase
counter, the bit-braid `(c>>2)&0x3F`, `((l&0x3)<<4)|((c>>4)&0xF)`, the two-pad /
one-pad tail) against the provided `BASE64EN` table.

## Why this matters — the trajectory

| Library | Domain | Repair needed to reach byte-exact |
|---|---|---|
| zlib (checksums→inflate) | compression | heavy — hand-porting, per-fn oracles, months |
| jsmn | JSON parser | multi-round surgical loop + **1 diagnosis** (loop-cursor idiom) |
| **base64** | **codec** | **none — first fill, 32/32** |

The line is bending the right way. jsmn proved the *machine* turns on a new
library; base64 proves the *idiom catalog* pays for itself — the mechanics that
took diagnosis to discover on zlib/jsmn (coherent out-param→`Vec` return, table
indexing, constant handling) now land on the first try somewhere new.

## What this proves (and doesn't)

**Proves:** the catalog generalizes. A never-seen library in a new domain
translated first-shot, fully autonomously, byte-exact. The compounding is real
and measured, not asserted.

**Doesn't yet prove:** first-shot on a library with *hard byte-exact algorithm
logic* (deflate_fast-class). base64's logic is modest; that's why it's a clean
breadth win, not a claim about the logic frontier. The tables were provided as
data (as the coherent type model is) — variant/table *inference* from the C is a
separate step. And this is one codec; the next libraries will surface new gaps,
which become new catalog entries.

The honest headline: **mechanics are now handled well enough that a simple new
library needs no repair at all.** That's exactly the bet behind "get faster the
more we prep" — and here it is, paid out.
