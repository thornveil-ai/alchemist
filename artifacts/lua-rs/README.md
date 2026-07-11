# artifacts/lua-rs — HAND-WRITTEN feasibility reference (NOT converter output)

**Important:** these crates were hand-written while exploring Phase C. They are
**not** produced by Alchemist and are **not** the deliverable. Alchemist's job is
autonomous C→Rust conversion; the actual Lua→Rust translation must be produced
**by the model pipeline**, gated by the whole-program differential oracle
(`alchemist/verifier/e2e_oracle.py`) over the corpus in `subjects/lua/oracle/`.

What is kept here for value:
- `ARCHITECTURE.md` — the ADRs (TValue→enum, GC→Rc scope, numeric byte-exactness)
  that inform how the converter should assemble the shared type-universe crate.
- The crates themselves — a reference proving byte-exact Lua-in-safe-Rust is
  achievable, and a source of oracle-verified golden expectations.

The mission is the converter, not this hand-written code. See
`alchemist/verifier/e2e_oracle.py` for the general capability that lets the
converter translate whole cyclic programs (Lua core, PX4, …) autonomously.
