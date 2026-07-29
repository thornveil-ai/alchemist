# The teacher-corpus flywheel

> How Alchemist gets its local model good enough to reach hard code — **without**
> violating the one rule (`docs/GROUNDING.md`): *the model writes the translation;
> you never hand-write the product.*

## Why this exists

Alchemist's product is a **model-driven** converter: point it at C, the local model
writes the Rust, the differential oracle proves it byte-exact or refuses. That works
today for the overwhelming majority of leaf and mid-complexity functions — see the
numbers below.

But some functions are genuinely beyond the current local model in one shot:
130-bit modular arithmetic (Poly1305), 256-bit field arithmetic + a Montgomery ladder
(X25519), a cyclic bytecode interpreter core (Lua). For those, "just prompt harder"
doesn't close the gap. **Fine-tuning the local model does.** And a fine-tune needs
training data: verified, byte-exact `(C, Rust)` pairs.

That training set is the **corpus** (`corpus/pairs.jsonl`). This doc is its charter.

## The rule, restated precisely

`GROUNDING.md` says: **never hand-write the translation output.** That rule is about
the **product** — the Rust the pipeline ships for a user's `alchemist translate`. It is
absolute. A hand-written `.rs` must never be passed off as, or spliced into, pipeline
output.

The corpus is a **different artifact with a different purpose**: it is *teacher data*,
not product. A small fraction of it is hand-written by a frontier model (Claude) as a
**worked example for the local model to learn from** — the same way a textbook prints
worked solutions. Every such pair is:

- **Tagged** `won_via: "frontier-claude"` — never silently mixed with model wins.
- **Verified byte-exact through the exact same differential oracle** the product uses
  (2000+ fuzzed inputs vs the compiled C reference) + published KATs. A frontier pair
  that fails the oracle is not banked. It earns its place by the same proof as any
  model win — the only difference is who drafted it.
- **Public-C only** (IL5): the frontier teacher only ever sees public-domain / open
  reference implementations. Never proprietary or sensitive source.

So: **hand-writing is forbidden as product output; sanctioned as tagged, oracle-verified
teacher data.** The two never touch.

## The flywheel

```
   new C API shape
        │
        ▼
   build an oracle LEVER  ──────────────►  the differential can now GATE this shape
        │                                   (this is the real, permanent product work)
        ▼
   point the LOCAL MODEL at it (`solo`)
        │
        ├─ model produces it byte-exact ──►  bank as a MODEL win (single/multi_sample).
        │                                    DONE. No hand-writing. This is the goal.
        │
        └─ model can't yet ──►  frontier-crack it (Claude hand-writes, oracle-verifies)
                                 ──►  bank as teacher data (frontier-claude)
                                       │
                                       ▼
                                 fine-tune the local model on the corpus
                                       │
                                       ▼
                                 model now does that class unaided  ──►  loop closes
```

The permanent value is the **lever** (it makes a whole shape gateable forever) and the
**fine-tuned model** (it makes the whole shape *translatable* forever). The frontier
crack is the transient scaffold in between.

### Proof the loop closes

**ChaCha20 and Salsa20** were first frontier-cracked (hand-written) as teacher data.
Then, once the `stream_xor` oracle lever existed **and** a harness bug was fixed (the
fill prompt was flooding the model with 9 KB of random-hex fuzz vectors → empty
completions), the **local model produced byte-exact ChaCha20 and Salsa20 on its own,
first `solo` iteration, verified over 2000 cases — with no fine-tune at all.** The
frontier cracks turned out to be teacher-data insurance; the actual blocker was a
harness bug, exactly as `GROUNDING.md` predicts ("the model is not the bottleneck; the
harness is"). That is the loop working: build lever → point model at it → the model does
the machine's job.

## Current state (2026-07-29)

`corpus/pairs.jsonl` — 351 verified byte-exact pairs:

| Source | Pairs | % | What |
|---|---:|---:|---|
| **Local model** (`single` / `multi_sample` / `cached`) | 335 | **95.4%** | the model already does the vast majority unaided |
| **Frontier teacher** (`frontier-claude`) | 16 | 4.6% | the hard tail: 130-bit/field crypto + hard fixed-point div |

The 16 frontier pairs are exactly the model's current frontier: WjCryptLib
SHA-256/1/512 + MD5 + RC4, B-Con AES/DES/Blowfish + MD2 + base64, ChaCha20, Salsa20,
Poly1305, and libfixmath `fix16_div`/`sdiv`/`mod`. Two of those (ChaCha20, Salsa20) the
model has since been shown to do unaided (see above) — they stay banked as teacher data
but no longer represent a capability gap.

## Oracle levers built for this (the durable product work)

Each lever lets the differential oracle **gate a new C API shape** — the thing that
makes byte-exact-or-refuse possible for that shape, whether the model or a frontier
teacher drafts it:

- **ctx-digest** (`init`/`update`/`final` hash contexts) + digest-len fallback +
  struct-wrapped-digest / `void*` buffer variants — SHA/MD/BLAKE families.
- **cipher-sequence** (keyed stream keystream, RC4-shaped, with drop-N + `void*`).
- **block-cipher** — three key-schedule carriers: struct (Blowfish), `WORD[]`+keysize
  (AES), 2-D schedule + enum (DES).
- **codec_io** — encode/decode byte-codec roundtrip (base64).
- **stream_xor** — keyed stream cipher `f(key, nonce, counter, in, out, len)`
  (ChaCha20/Salsa20); wired into **both** the differential and the fill-loop fuzz
  vectors so the model can be scored on it.
- **mac** — one-shot authenticator `f(tag, msg, len, key)` (Poly1305; reusable for
  HMAC/GMAC).

## Do / don't

- **Do** build a lever for a new shape, then point the local model at it first.
- **Do** frontier-crack only what the model provably can't, tag it `frontier-claude`,
  and verify it through the oracle like anything else.
- **Do** treat the corpus as fuel for a fine-tune — its purpose is to be *trained on*,
  not to grow forever by hand.
- **Don't** splice a hand-written translation into pipeline output. Ever.
- **Don't** let frontier-cracking substitute for the product metric — *whole-library,
  hands-off, low refusal* (see the roadmap). Corpus growth is a means; that metric is
  the end.
