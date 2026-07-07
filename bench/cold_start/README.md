# Cold-start benchmark (Phase 0 instrumentation)

The honest, repeatable measure of **how far the shipping pipeline gets on never-seen C,
cold, with zero human touches.** This is the regression gate for every future pipeline
change: the numbers in `RESULTS.md` must go **up**, never down.

## What it does
`cold_bench.py` embeds a suite of self-contained C functions across classes
(math, bits, checksum, string, parser, stateful cipher/PRNG/allocator), writes each into
`bench/cold_start/<name>/<name>.c`, runs `alchemist translate` on each **cold** (no config,
no oracle hand-off), and scores how far each gets:

- `triage` — did the classifier *attempt* it, or skip it as "glue" (0 LLM calls)?
- per-stage PASS/FAIL — analyze / extract / architect / implement / verify
- `overall` — did it produce verified (differential-passing) safe Rust with no human input?

Outputs `RESULTS.md` (scorecard) + `results.json` (raw).

## How to run (regression gate)
Requires the model endpoint up (local Gemma via vLLM) and the alchemist venv:

```bash
# on the box (or any host with the pipeline + a local model endpoint):
export ALCHEMIST_ENDPOINT=http://127.0.0.1:8086/v1   # your local endpoint
export ALCHEMIST_ROOT=/path/to/alchemist              # repo root (defaults to cwd)
.venv/bin/python bench/cold_start/cold_bench.py
```

It takes ~8–12 min (one full cold translate per function). Compare the new `RESULTS.md`
against the committed baseline; a drop in "triaged in", "passed verify", or "overall pass"
is a regression.

> Note: this cannot run in stock CI (no local model in CI). It is a **manual/local
> regression gate** run on the box before/after pipeline changes. The committed baseline is
> the number to beat.

## Baseline (2026-07-07)
- Triaged in: **12%** · Passed implement: **12%** · Passed verify: **0%** · Overall: **0%**
- Takeaway: WALL 1 (triage skips unknown code) blocks 7/8; even the one attempt missed the
  differential. See `RESULTS.md` and `docs/BATTLE_PLAN.md` Phase 1.

## Extending the suite
Add a `(name, class, c_source)` tuple to `SUITE` in `cold_bench.py`. Keep each function
self-contained and deterministic (pure or state-mutating) so a differential oracle is
well-defined.
