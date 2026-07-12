# Leaf-function benchmark (P0.11)

The honest, repeatable measure of Alchemist's reach on unseen pure C leaf
functions. 23 self-contained functions spanning the shape spectrum:

| category  | n  | shape / oracle |
|-----------|----|----------------|
| checksum  | 8  | seeded/unseeded buffer hash → `classify_checksum` |
| scalar    | 10 | bit/int fns (1–2 args) → `classify_scalar` |
| cstr      | 3  | `char* f(char*)` string transforms → `classify_cstr_out` (P0.8a) |
| uncovered | 2  | intentionally not-yet-covered shapes → honest refusals |

## Regenerate the corpus
```
python bench/leaf/gen_corpus.py
```
The `.c` files under `subjects/` are committed (fixed benchmark input);
`gen_corpus.py` is the compact source of truth.

## Run (needs a model + gcc + cargo — the box)
```
ALCHEMIST_ENDPOINT=http://localhost:8086/v1 \
  .venv/bin/python bench/leaf/run_leafbench.py
```
Aggregates the per-run refusal ledgers (P0.7) into `scorecard.json` and prints
verified / first-pass / refusal rates, overall and per category.

The `uncovered` category is expected to refuse — it measures coverage gaps
honestly, not failures.
