> **⚠️ MIXED / partly historical.** This guide references both shipping engines and
> orphaned `alchemist/autonomy/` modules. For real onboarding, route through the CLI:
> `alchemist analyze → extract → architect → implement → verify`. The
> `alchemist.autonomy.*` module runners it mentions are the superseded research track
> (see [GROUNDING.md](GROUNDING.md)); of those, only `shim_synth` is on the salvage list.

# Onboarding a new C library — the repeatable playbook

The goal of this doc: make library **N+1** fast. zlib was the bring-up (slow,
lots of hand-tooling). Everything that was zlib-*specific* has been — or is being
— turned into library-*agnostic* machinery, so each new library reuses the
engines and only pays for what's genuinely new.

This is the "get faster with prep" ledger: **what's reusable, what's per-library,
and the exact sequence to run.**

---

## What's already agnostic (reuse for free)

These carry over to any library with zero per-library code:

| Engine | Module | What it does |
|---|---|---|
| Differential-oracle discipline | `verifier/` | byte-exact-or-refused — the correctness guarantee |
| WS4 diagnose-and-repair loop | `autonomy/repair.py`, `regen_batch.py` | stub → model refill from C → verify → ledger; iterative error feedback; baseline-delta oracle |
| WS1 shim generator | `autonomy/shim_synth.py` + `c_struct.py` | field accessors + call-through runners auto-generated **from the header's struct** (no hardcoded field table) |
| WS6 idiom catalog | `catalog/` | C→safe-Rust patterns injected per function by C-signal match; grows per library |
| Extractor robustness | `implementer/reference_probe.py` | brace-match fallback recovers huge macro-heavy functions tree-sitter chokes on |
| Autonomy scorecard | `autonomy/scorecard.py` | inventories remaining human-supplied debt, tracks retirements |

**Rule of thumb:** if it reads structure from the C source/headers, it's agnostic.
If it encodes a specific type/field/name, it needs to become a parser (like
`c_struct.py` replaced the hardcoded `DEFLATE_STATE_TYPES`).

---

## The onboarding sequence

1. **Acquire + gate.** Clone the library. Confirm it's a *valid target*:
   - builds from source with a standard toolchain, and
   - is **deterministic** (no wall-clock/rand/threads/IO in the functions under
     test, no reliance on UB). If not, the honest move is to **refuse** or scope
     to the deterministic subset. Don't oracle non-determinism.

2. **Build the reference.** Compile the C into a shared lib. (WS5, still partly
   manual: detect make/cmake/autotools. zlib was pre-built; generalizing this is
   the next WS5 task.)

3. **Analyze + extract.** Run the pipeline's analyze→extract to get the function
   inventory, signatures, and struct graph.

4. **Synthesize the oracle harness.**
   - Simple/pure functions → `verifier/auto_ffi` FFI bindings.
   - Stateful functions → `shim_synth.field_types_from_header(header, StructName)`
     then generate accessors + call-through runners. Compile-validate each as a
     drop-in (per-accessor fallback keeps only what compiles).

5. **Coherent type model (WS2 — the main per-library cost today).** Decide the
   owned-Rust representation of the C pointer graph: buffer model (drained Vec vs
   offset), ownership tree (who owns the state), aliasing bridges (`mem::take`),
   union handling. On zlib this was hand-specified; automating it (ownership/
   aliasing *inference*) is the deepest open workstream.

6. **Translate + verify (WS4).** Run `regen_batch`/the TDD loop: model fills each
   function from C + idioms + struct context; the differential oracle gates it;
   the repair loop iterates on the exact discrepancy; retirements land in the
   ledger. Control-flow-heavy functions (goto/state machines) may need the WS3
   structuring assist (today: a hand-written skeleton; general auto-structuring
   is unbuilt).

7. **Score.** `python -m alchemist.autonomy.scorecard --subject <lib>` — the
   remaining human-supplied debt, classified by workstream. Drive it down.

---

## What still costs per-library effort (be honest)

Ranked by how much it hurts today:

1. **WS2 coherent model / ownership inference** — the biggest manual cost. Until
   ownership+aliasing inference exists, a human decides the type model.
2. **WS3 control-flow structuring** — `goto`/state machines still need a
   skeleton for the hardest functions (e.g. a driver like `inflate()`).
3. **WS5 build/harness detection** — wiring the C build + oracle compile.
4. **Custom shims** — the non-mechanical setup/marshalling glue (`fw_init`-style)
   the generator doesn't yet cover.
5. **The hard-function tail** — complex stateful functions the model resists;
   they need higher-effort refills or decomposition.

---

## Checklist for library N+1

- [ ] Builds from source; deterministic (or scoped to the deterministic subset)
- [ ] Reference shared lib compiled
- [ ] Struct(s) parse cleanly via `c_struct.parse_struct_fields`
- [ ] Oracle shims generated + compile-validated from the header
- [ ] Coherent type model decided (WS2) — the one real design step
- [ ] Idiom catalog reviewed; new idioms added for this library's patterns
- [ ] `regen_batch` run; ledger populated; scorecard trending down
- [ ] Anything unprovable is **refused and reported**, never faked

---

## Time-savers learned from zlib (don't relearn these)

- **Parse structure, don't hardcode it.** Every hardcoded field/type/name is a
  future per-library tax; turn it into a parser once.
- **Iterate on the exact error.** The single biggest WS4 win was feeding the
  compiler/test error back so the model fixes the *cause* (e.g. "`put_short`
  doesn't exist → inline to `state.pending.push`").
- **Baseline-delta, not all-green.** A crate with unrelated stale failures is
  still a valid regen target if the failing-test set returns to baseline.
- **Isolate per-function tests** so unrelated failures don't mask a real repro.
- **Compile-validate generated glue** as a drop-in; keep only what compiles.
- **Refuse honestly.** The one shim that wouldn't compile as a drop-in
  (`send_bits`, a macro) stayed on the books. Trust comes from the "no"s.
