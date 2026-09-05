# Alchemist

**Algorithm-aware C-to-Rust translation with a proof obligation.**

Point it at C. Get back safe Rust that has been proved byte-identical to the compiled
original — or get a refusal that names the function and says exactly what could not be
established. Nothing in between. Nothing leaves your machine.

[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![status](https://img.shields.io/badge/status-research--prototype-yellow.svg)](PRODUCTION_READINESS.md)
[![zlib](https://img.shields.io/badge/zlib-byte--exact%20round--trip-brightgreen.svg)](docs/zlib_case_study.md)

---

```
$ alchemist translate ./my-c-lib --name my-rs

  [PASS] analyze     78 files, 412 fns, 9 modules
  [PASS] extract     specs OK
  [PASS] architect   7-crate workspace validated
  [PASS] implement   TDD: 411/412 fns pass tests
  [PASS] verify      compile ✓  anti-stub ✓  no-unsafe ✓  cargo test ✓  differential (10K/10K) ✓
  [PASS] report      metrics + receipt written

  OVERALL: PASS      wall-time: 11m 42s      cost: $0.00
```

The cost line is not a rounding error. The model runs on your GPU.

---

## The one idea

Most C-to-Rust tools optimise for producing output. Alchemist optimises for **being right about
whether the output is correct**.

Every translated function is executed against the *compiled original* over thousands of
generated inputs — not a golden file, not the model's opinion, the actual `.so` built from your
C. Disagree on one byte and the function does not ship. It gets an `unimplemented!` carrying the
reason, and the run says so out loud.

That property is the product. A translator that is right 80% of the time and cannot tell you
*which* 80% is unusable for anything that matters. One that refuses out loud is something you
can build on.

---

## What it has actually done

**zlib — compressor and decompressor — in pure safe Rust, proved by a full byte-exact
round-trip.**

```
Rust deflate  →  Rust inflate  →  the original bytes        (identical, 21/21)
```

- `deflate` byte-exact against the reference C at levels 1–9, plus `Z_HUFFMAN_ONLY` and `Z_RLE`
- `inflate` byte-exact on stored, fixed and dynamic Huffman streams, LZ77 back-references intact
- **Zero `unsafe`.** A ~30-state decode machine, `goto` spaghetti, `union`s, pointer aliasing and
  bit-level packing — all re-expressed inside Rust's ownership model, not transliterated around it

The part worth noticing is what the oracle caught on the way: **roughly nine real integration
bugs** that every isolated unit test passed clean over. A whole-state wipe. A shift overflow. A
pointer-aliasing gap that only appeared once two correct-looking functions were composed.
Byte-exact-or-refuse is not ceremony — it finds things unit tests structurally cannot.

→ **[Full write-up, including where it falls down](docs/zlib_case_study.md)**

The translation corpus stands at **351 verified `(C, Rust)` pairs**, **95% authored by the local
model** rather than a frontier one. Every pair clears the same differential regardless of who
drafted it — provenance is recorded, never assumed.

---

## What makes this hard

C says things Rust's type system will not repeat. The interesting work is in the gap:

| The C does | Rust has to |
|---|---|
| `goto` into the middle of a loop nest | become a state machine that provably matches |
| `union` reinterpretation and type punning | become explicit, bounded conversion |
| Two pointers into the same object | satisfy the borrow checker without changing behaviour |
| `static` state mutating across calls | carry that state without `unsafe` or a global |
| Read a buffer whose length is nowhere in the signature | know the real extent before it can be fuzzed |
| Signed overflow, out-of-range shifts — undefined | match the compiled reference *where it is defined*, and refuse to claim the rest |

Alchemist handles these as a **shape system**: a growing set of recognised C API shapes, each
with an oracle that knows how to drive it and compare it. Checksum and digest contexts. Keyed
stream ciphers. Block ciphers with a key schedule. Codec round-trips. One-shot authenticators.
Bare-pointer buffers with no length parameter. A shape the oracle cannot drive is refused, not
guessed at — which is why coverage grows by building levers, not by loosening standards.

---

## Verification, concretely

Six stages, then a gate stack that must pass before anything is called a translation:

| Stage | What it does |
|---|---|
| **analyze** | tree-sitter parse, call graph, algorithmic module detection |
| **extract** | recover a language-neutral spec per algorithm; constants pulled deterministically |
| **architect** | design and validate a Rust workspace — crates, shared types, ownership |
| **implement** | generate each function test-first, iterating against a real oracle |
| **verify** | the gates below, all mandatory |
| **report** | metrics, plus a receipt recording exactly what was proved |

The gates: **compiles clean** · **anti-stub** (no `todo!`, no placeholder bodies masquerading as
work) · **structural no-unsafe proof** · **semantic lints** · **`cargo test`** · **differential
equivalence against the compiled C**.

Fail-closed by construction: **no oracle means no claim.** A function whose behaviour cannot be
established is refused rather than guessed, and lands in a refusal ledger with its reason — so a
run's honest coverage is always legible, including to you six months later.

Where the C is undefined on part of its input space, Alchemist **narrows the claim instead of
overreaching**: it verifies across the defined domain, emits, and explicitly declines to assert
anything outside it. The receipt records the domain. A translation that quietly "fixed" your
undefined behaviour would be a different program wearing your program's name.

→ [Architecture](docs/architecture.md) · [Design grounding](docs/GROUNDING.md) · [API reference](docs/api_reference.md)

---

## Why local-only is a design decision

The code you most need to translate is usually the code you are least able to upload. Legacy
control systems. Regulated codebases. Anything under an export or classification regime.

So the model runs on your GPU, the oracle compiles and fuzzes on your machine, and nothing is
transmitted. That costs raw model capability — and buys the ability to run at all in the
environments where memory-unsafe C is most entrenched and most consequential.

It also keeps the pipeline **model-agnostic**. The LLM sits behind an interface; swapping it is
configuration, not a rewrite. Reasoning models, instruct models, whatever ships next year.

---

## Maturity

A **research prototype**, and the docs say so in detail rather than burying it.

Strong on leaf and mid-complexity functions across a wide range of C. Honest about what it
refuses. Whole-project translation at scale — thousands of functions, deep cross-module state —
is active work, not a shipped claim.

→ **[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)** is the unvarnished version. Read it
before forming an opinion.

---

## Install

```bash
git clone https://github.com/thornveil-ai/alchemist
cd alchemist && pip install -e .
alchemist --help
```

Python 3.12+, Rust 1.75+, and a local OpenAI-compatible endpoint.
[docs/tutorial.md](docs/tutorial.md) walks the first translation.

---

## Working on something related?

Built and maintained by **[Thornveil LLC](https://github.com/thornveil-ai)**.

The interesting problems here are not finished, and most of what has been learned lives in the
engineering rather than in a paper. If this overlaps with what you are doing, get in touch rather
than guessing from the source:

- **Translating a real codebase** and want to know whether this holds up on it
- **Evaluating C-to-Rust approaches** for a program or a team, and want the honest scope
- **Air-gapped or regulated environment** where cloud translation is a non-starter
- **Researching translation verification** — oracles, differential equivalence, principled refusal

📧 **jesse@thornveil.ai** · or [open an issue](https://github.com/thornveil-ai/alchemist/issues)

A C pattern that does not convert cleanly is genuinely useful to us. That is how the shape system
grows.

---

## Prior art

Alchemist stands on other people's work: c2rust for mapping what mechanical transpilation can and
cannot reach, and the wider research community for framing LLM-based translation rigorously
enough to be measured at all. Public C-to-Rust benchmark corpora have been valuable for
evaluating this against something we did not write ourselves.

## License

Apache-2.0. See [LICENSE](LICENSE).

A Thornveil system. See [other Thornveil systems](https://github.com/thornveil-ai).
